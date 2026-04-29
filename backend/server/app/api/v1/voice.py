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
    
    # For voice mode, we must strip all reasoning/thought rules to prevent audio narration
    # of internal logic. We use a more robust multi-line replacement strategy.
    voice_system_prompt = system_prompt
    for rule_to_remove in [
        "1. PROACTIVE DATA GATHERING:",
        "2. STEP-BY-STEP THOUGHT:",
        "ALWAYS start your response with your internal thought process wrapped in `<thought>` tags.",
        "Explain your plan, including which tool you will use and why.",
        "Always think step by step before using any tool.",
    ]:
        # Remove the rule and its likely surrounding context
        import re
        voice_system_prompt = re.sub(rf".*?{re.escape(rule_to_remove)}.*?\n", "", voice_system_prompt, flags=re.IGNORECASE)

    # Add voice-specific instructions at the top
    voice_system_prompt = (
        "You are in VOICE MODE. Respond naturally and concisely like a human assistant.\n"
        "NEVER narrate tool calls, reasoning, or thought processes aloud.\n"
        "If you use a tool, wait for the result and then speak only the final answer.\n\n"
        + voice_system_prompt
    )
    
    history = await session_store.get_history(session_id)
    # We pass history as a text prompt prefix to ensure compatibility and stability
    history_text = "Here is the conversation history so far:\\n"
    for msg in history:
        role = "User" if msg.__class__.__name__ == "HumanMessage" else "FarmShield Assistant"
        history_text += f"{role}: {msg.content}\\n"
    
    # Add voice mode directive
    full_system_instruction = voice_system_prompt + "\n\nIMPORTANT: You are in VOICE MODE. Speak concisely, naturally, and never narrate tool calls or reasoning." + "\n\n" + history_text
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part.from_text(text=full_system_instruction)]),
        tools=[sql_database_schema, sql_database_query, search_farming_knowledge],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    transcript_buffer = []
    user_transcript_buffer = []
    
    # Event to signal graceful shutdown
    shutdown_event = asyncio.Event()
    
    try:
        async with client.aio.live.connect(model=settings.voice_model, config=config) as session:
            
            async def receive_from_browser():
                """Stream audio from browser to Gemini Live API."""
                try:
                    while not shutdown_event.is_set():
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
                                    logger.info("voice_cancel_requested", session_id=session_id)
                                    break
                        except WebSocketDisconnect:
                            logger.info("voice_ws_disconnected_by_client", session_id=session_id)
                            break
                        except json.JSONDecodeError as e:
                            logger.warning("voice_invalid_json_from_browser", error=str(e))
                            # Don't break; just skip this message
                        except asyncio.CancelledError:
                            logger.debug("browser_receive_cancelled")
                            raise
                        except RuntimeError as e:
                            # "Cannot call "receive" once a disconnect message has been received."
                            if "disconnect" in str(e).lower():
                                logger.info("voice_ws_already_disconnected", session_id=session_id)
                                break
                            logger.error("voice_browser_receive_error", error=str(e))
                        except Exception as e:
                            logger.error("voice_browser_receive_error", error=str(e))
                            # Continue on transient errors; only break on disconnect
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error("browser_receive_fatal_error", error=str(e))

            async def receive_from_genai():
                """Stream responses from Gemini Live API to browser."""
                try:
                    async for response in session.receive():
                        if shutdown_event.is_set():
                            logger.debug("genai_receive_shutdown_signaled")
                            break
                            
                        try:
                            if response.server_content:
                                # 1. Handle Model Transcript
                                if hasattr(response.server_content, "output_transcription") and response.server_content.output_transcription:
                                    text_chunk = response.server_content.output_transcription.text
                                    if text_chunk:
                                        transcript_buffer.append(text_chunk)
                                        try:
                                            await websocket.send_json({"event": "transcript", "text": text_chunk})
                                        except Exception as e:
                                            logger.warning("transcript_send_failed", error=str(e))

                                # 2. Handle User Transcript
                                if hasattr(response.server_content, "input_transcription") and response.server_content.input_transcription:
                                    text_chunk = response.server_content.input_transcription.text
                                    if text_chunk:
                                        user_transcript_buffer.append(text_chunk)
                                        try:
                                            await websocket.send_json({"event": "user_transcript", "text": text_chunk})
                                        except Exception as e:
                                            logger.warning("user_transcript_send_failed", error=str(e))

                                # 3. Handle Audio Playback
                                model_turn = response.server_content.model_turn
                                if model_turn:
                                    for part in model_turn.parts:
                                        if part.inline_data:
                                            try:
                                                await websocket.send_bytes(part.inline_data.data)
                                            except Exception as e:
                                                logger.warning("audio_send_failed", error=str(e))
                                        
                                if response.server_content.turn_complete:
                                    try:
                                        await websocket.send_json({"event": "turn_complete"})
                                    except Exception as e:
                                        logger.warning("turn_complete_send_failed", error=str(e))
                                
                            elif response.tool_call:
                                logger.info("voice_tool_call_received", calls=len(response.tool_call.function_calls))
                                tool_responses = []
                                for tc in response.tool_call.function_calls:
                                    try:
                                        name = tc.name
                                        args = tc.args
                                        
                                        # Send reasoning event to frontend (non-critical)
                                        try:
                                            await websocket.send_json({
                                                "event": "reasoning",
                                                "text": f"Calling tool: **{name}** with arguments: `{json.dumps(args)}`\n"
                                            })
                                            await websocket.send_json({
                                                "event": "sources",
                                                "sources": [name]
                                            })
                                        except Exception as e:
                                            logger.debug("reasoning_send_failed", error=str(e))

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
                                logger.info("voice_sending_tool_responses", count=len(tool_responses))
                                await session.send_tool_response(function_responses=tool_responses)
                            else:
                                # Log unhandled response types to diagnose early termination
                                logger.warning("voice_unhandled_genai_response", response=str(response)[:200])
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            logger.error("genai_response_processing_error", error=str(e))
                            # Continue processing other responses
                            
                except asyncio.CancelledError:
                    logger.debug("genai_receive_cancelled")
                    raise
                except Exception as e:
                    logger.error("genai_receive_fatal_error", error=str(e))

            async def heartbeat():
                """Keep-alive ping every 15s. Exit cleanly on shutdown or websocket close."""
                try:
                    while not shutdown_event.is_set():
                        try:
                            await asyncio.wait_for(shutdown_event.wait(), timeout=15.0)
                            break  # Shutdown signaled
                        except asyncio.TimeoutError:
                            pass  # 15 seconds elapsed, send heartbeat
                        
                        # Send ping only if websocket is still connected
                        try:
                            if websocket.client_state.value == 1:  # CONNECTED
                                await websocket.send_json({"event": "ping", "ts": int(time.time())})
                        except Exception as e:
                            logger.debug("heartbeat_send_failed", error=str(e))
                            # Don't exit on heartbeat failure; just skip this ping
                            
                except asyncio.CancelledError:
                    logger.debug("heartbeat_cancelled")
                    raise
                except Exception as e:
                    logger.error("heartbeat_error", error=str(e))

            # Start all three tasks
            t1 = asyncio.create_task(receive_from_browser())
            t1.set_name("browser_receive")
            t2 = asyncio.create_task(receive_from_genai())
            t2.set_name("genai_receive")
            t3 = asyncio.create_task(heartbeat())
            t3.set_name("heartbeat")
            
            tasks = [t1, t2, t3]
            
            try:
                # Wait for EITHER browser_receive OR genai_receive to finish (not heartbeat)
                # These are the critical tasks; if either finishes, the conversation is over
                done, pending = await asyncio.wait(
                    [t1, t2],  # Only watch these two; heartbeat is independent
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Log which task finished
                for task in done:
                    try:
                        res = task.result()
                        logger.info("voice_critical_task_finished", task=task.get_name(), result=res)
                    except Exception as e:
                        logger.error("voice_critical_task_error", task=task.get_name(), error=str(e))
                
                logger.info("voice_session_ending", session_id=session_id, reason="critical_task_complete")
                
            finally:
                # Graceful shutdown: signal heartbeat to stop
                shutdown_event.set()
                
                # Cancel all pending tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                
                # Give tasks a moment to clean up
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.debug("task_cleanup_error", error=str(e))
                
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
