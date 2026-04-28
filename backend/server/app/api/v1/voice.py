"""
FarmShield Chat — Voice WebSocket (Amendment 1).
Routes audio from browser to Gemini Live API and back.
"""

import asyncio
import json
import structlog
import traceback
import time
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from google import genai
from google.genai import types

from app.config import settings
from app.services.chat.session_store import session_store
from app.services.chat.agent import farm_agent, SYSTEM_PROMPT

logger = structlog.get_logger(__name__)
router = APIRouter()

def sql_database_schema(table_names: str) -> str:
    """Inspect table schemas before writing SQL."""
    try:
        return farm_agent.sql_tools[0].invoke(table_names)
    except Exception as e:
        return f"Error: {e}"

def sql_database_query(query: str) -> str:
    """Run SQL queries against live sensor data."""
    try:
        return farm_agent.sql_tools[1].invoke(query)
    except Exception as e:
        return f"Error: {e}"

def search_farming_knowledge(query: str) -> str:
    """Search the FarmShield agricultural knowledge base."""
    try:
        return farm_agent.rag_tool.invoke(query)
    except Exception as e:
        return f"Error: {e}"

@router.websocket("/chat/voice/ws")
async def voice_websocket(
    websocket: WebSocket,
    session_id: str = Query(...),
    language: Optional[str] = Query(None)
):
    await websocket.accept()
    
    if not settings.voice_enabled:
        await websocket.send_json({"event": "error", "message": "Voice chat is disabled."})
        await websocket.close()
        return

    logger.info("voice_session_started", session_id=session_id)
    
    client = genai.Client(api_key=settings.gemini_api_key)
    system_prompt = settings.voice_system_prompt_override or SYSTEM_PROMPT.format(device_id=settings.mqtt_client_id)
    
    history = await session_store.get_history(session_id)
    # We pass history as a text prompt prefix to ensure compatibility and stability
    history_text = "Here is the conversation history so far:\\n"
    for msg in history:
        role = "User" if msg.__class__.__name__ == "HumanMessage" else "FarmShield Assistant"
        history_text += f"{role}: {msg.content}\\n"
    
    full_system_instruction = system_prompt + "\\n\\n" + history_text
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(text=full_system_instruction)]),
        tools=[sql_database_schema, sql_database_query, search_farming_knowledge],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    transcript_buffer = []
    user_transcript_buffer = []
    
    try:
        async with client.aio.live.connect(model=settings.voice_model, config=config) as session:
            
            async def receive_from_browser():
                while True:
                    try:
                        message = await websocket.receive()
                        if "bytes" in message:
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    mime_type="audio/pcm;rate=16000",
                                    data=message["bytes"]
                                )
                            )
                        elif "text" in message:
                            data = json.loads(message["text"])
                            if data.get("event") == "end_of_speech":
                                await session.send_client_content(
                                    turns=[types.Content(role="user", parts=[types.Part.from_text(text="I have finished speaking.")])],
                                    turn_complete=True
                                )
                            elif data.get("event") == "cancel":
                                break
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error("voice_ws_receive_error", error=str(e))
                        break

            async def receive_from_genai():
                async for response in session.receive():
                    if response.server_content:
                        # 1. Handle Model Transcript
                        if hasattr(response.server_content, "output_transcription") and response.server_content.output_transcription:
                            text_chunk = response.server_content.output_transcription.text
                            if text_chunk:
                                transcript_buffer.append(text_chunk)
                                await websocket.send_json({"event": "transcript", "text": text_chunk})

                        # 2. Handle User Transcript
                        if hasattr(response.server_content, "input_transcription") and response.server_content.input_transcription:
                            text_chunk = response.server_content.input_transcription.text
                            if text_chunk:
                                user_transcript_buffer.append(text_chunk)
                                await websocket.send_json({"event": "user_transcript", "text": text_chunk})

                        # 3. Handle Audio Playback
                        model_turn = response.server_content.model_turn
                        if model_turn:
                            for part in model_turn.parts:
                                if part.inline_data:
                                    await websocket.send_bytes(part.inline_data.data)
                                    
                        if response.server_content.turn_complete:
                            await websocket.send_json({"event": "turn_complete"})
                            
                    elif response.tool_call:
                        tool_responses = []
                        for tc in response.tool_call.function_calls:
                            try:
                                name = tc.name
                                args = tc.args
                                
                                # Send reasoning event to frontend
                                try:
                                    await websocket.send_json({
                                        "event": "reasoning",
                                        "text": f"Calling tool: **{name}** with arguments: `{json.dumps(args)}`\n"
                                    })
                                except:
                                    pass

                                # Run synchronous tools in a thread to avoid blocking the event loop
                                if name == "sql_database_schema":
                                    res = await asyncio.to_thread(sql_database_schema, args.get("table_names", ""))
                                elif name == "sql_database_query":
                                    res = await asyncio.to_thread(sql_database_query, args.get("query", ""))
                                elif name == "search_farming_knowledge":
                                    res = await asyncio.to_thread(search_farming_knowledge, args.get("query", ""))
                                else:
                                    res = "Tool not found"
                                
                                tool_responses.append(
                                    types.FunctionResponse(
                                        name=name,
                                        id=tc.id,
                                        response={"result": res}
                                    )
                                )
                            except Exception as e:
                                logger.error("tool_execution_error", name=tc.name, error=str(e))
                                tool_responses.append(
                                    types.FunctionResponse(
                                        name=tc.name,
                                        id=tc.id,
                                        response={"error": str(e)}
                                    )
                                )
                        await session.send_tool_response(function_responses=tool_responses)

            async def heartbeat():
                while True:
                    try:
                        await asyncio.sleep(15)
                        if websocket.client_state.value == 1: # CONNECTED
                            await websocket.send_json({"event": "ping", "ts": int(time.time())})
                        else:
                            break
                    except:
                        break

            # Wait for any to finish
            t1 = asyncio.create_task(receive_from_browser())
            t1.set_name("browser_receive")
            t2 = asyncio.create_task(receive_from_genai())
            t2.set_name("genai_receive")
            t3 = asyncio.create_task(heartbeat())
            t3.set_name("heartbeat")
            
            tasks = [t1, t2, t3]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            # Log which task finished first
            for task in done:
                try:
                    res = task.result()
                    logger.info("voice_task_finished", task=task.get_name(), result=res)
                except Exception as e:
                    logger.error("voice_task_error", task=task.get_name(), error=str(e))
            
            for p in pending:
                p.cancel()
            logger.info("voice_session_closing", session_id=session_id)
                
    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("voice_api_error", error=str(e))
        traceback.print_exc()
        try:
            await websocket.send_json({"event": "error", "message": "Voice API error occurred."})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
        final_text = "".join(transcript_buffer)
        final_user_text = "".join(user_transcript_buffer)
        
        # Save to history
        if final_user_text or final_text:
            user_msg = final_user_text if final_user_text else "[Voice Message]"
            ai_msg = final_text if final_text else "[Voice Response]"
            await session_store.append(session_id, user_msg, ai_msg)
