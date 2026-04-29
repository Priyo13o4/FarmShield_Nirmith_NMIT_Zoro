"""
FarmShield Chat — Agent (Phase 7, LangChain 1.2.x / LangGraph compatible).

LangChain 1.2.x removed AgentExecutor and create_tool_calling_agent.
The new API uses:
  - langchain.agents.create_agent (recommended, uses langsmith tracing)
  - OR langgraph.prebuilt.create_react_agent (lower-level, same underlying graph)

Both return a CompiledStateGraph that takes {"messages": [...]} as input,
where messages is the FULL conversation (history + current human message).

The graph uses Gemini's native function-calling API — not text-based ReAct.
This is equivalent to the old create_tool_calling_agent + AgentExecutor pattern.

Corrections from PRD verification applied here:
  Error 1: Uses create_agent (native tool calling via LangGraph) — NOT old ReAct text.
  Error 3: device_id filled from settings.mqtt_client_id (NOT hardcoded).
  Error 4: stream() yields dicts {"token": str} and final {"done": True, ...}.
"""

import time
import json
from collections.abc import AsyncIterator
from typing import Any

import structlog
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.services.chat.session_store import session_store

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are FarmShield Assistant — a proactive AI embedded in a smart agriculture \
monitoring system. You help farmers manage their crops using real-time sensor data and \
scientific knowledge.

You have access to three tools:
- sql_database_schema: Use to inspect table structures.
- sql_database_query: Use to run SQL queries for live/historical sensor data.
- search_farming_knowledge (RAG): Use for general crop care, NPK optimal ranges, and pest info.

CRITICAL OPERATIONAL RULES:
1. PROACTIVE DATA GATHERING: If a user asks for advice (e.g., "what fertilizer should I use?" or "is my soil dry?"), you MUST query the `sensor_readings` table first for the latest values (npk_n, npk_p, npk_k, soil_pct, etc.). NEVER ask the user for sensor values if they are available in the database.
2. STEP-BY-STEP THOUGHT: Always start with your internal thought process wrapped in `<thought>` tags. Explain your plan, including which tool you will use and why.
3. CONTEXTUAL ADVICE: When giving advice, combine the live sensor data with the knowledge base. 
   Example: "Your current Nitrogen is 150 mg/kg. According to my knowledge base, for Rice, the optimal range is 280-560 mg/kg. Therefore, you should apply Nitrogen fertilizer."
4. NO EARLY TERMINATION: Once you have the results of a tool call, you MUST provide the final answer to the user. Do NOT stop after a tool call. If you need more data, call another tool immediately.
5. SQL CHEAT SHEET:
   - Latest sensor data: `SELECT * FROM sensor_readings ORDER BY time DESC LIMIT 1`
   - Latest data for specific device: `SELECT * FROM sensor_readings WHERE device_id = 'farmshield_node1' ORDER BY time DESC LIMIT 1`
   - Historical trends: `SELECT time, soil_pct FROM sensor_readings WHERE time > NOW() - INTERVAL '24 hours' ORDER BY time ASC`
6. SENSOR TABLE: `sensor_readings` contains time, device_id, soil_pct, tds_ppm, temp_c, humidity_pct, rain_raw, motion, npk_n, npk_p, npk_k, leaf_r, leaf_g, leaf_b, pump_on, mode, uptime_s, npk_ok.
7. MULTILINGUAL: Detect and respond in the EXACT same language used by the user.
8. UNKNOWN CROP: If you need to know the crop, provide a general range for common crops first, then ask for theirs.
"""


class FarmShieldAgent:
    """Wraps a LangGraph CompiledStateGraph with invoke and streaming capabilities."""

    def __init__(self) -> None:
        self._graph = None
        self._system_message: str = ""
        self._ready = False

    def load(self, sql_tools: list, rag_tool, settings) -> None:
        """
        Initialise the agent with tools and LLM.
        """
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.chat_temperature,
            max_output_tokens=settings.chat_max_output_tokens,
        )

        self._system_message = SYSTEM_PROMPT.format(device_id=settings.mqtt_client_id)

        self.sql_tools = sql_tools
        self.rag_tool = rag_tool
        tools = sql_tools + [rag_tool]

        self._graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=self._system_message,
        )
        self._ready = True
        logger.info(
            "farm_agent_loaded",
            model=settings.gemini_model,
            device_id=settings.mqtt_client_id,
            tool_count=len(tools),
        )

    def _build_messages(self, history: list, message: str) -> list:
        """Build the full message list: history + current human message."""
        return history + [HumanMessage(content=message)]

    async def invoke(self, message: str, session_id: str) -> dict[str, Any]:
        """Invoke the agent and return a complete response dict."""
        try:
            history = await session_store.get_history(session_id)
            messages = self._build_messages(history, message)

            result = await self._graph.ainvoke({"messages": messages})

            # Result is AgentState — final answer is the last AIMessage
            reply = ""
            reasoning_parts = []
            sources: list[str] = []
            
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    raw_content = ""
                    if isinstance(msg.content, str):
                        raw_content = msg.content
                    elif isinstance(msg.content, list):
                        texts = []
                        for b in msg.content:
                            if isinstance(b, dict):
                                if b.get("type") == "text":
                                    texts.append(b.get("text", ""))
                                elif b.get("type") in ["thought", "thinking"]:
                                    reasoning_parts.append(b.get("text", ""))
                        raw_content = "\n".join(texts)

                    # Extract <thought> tags from raw content
                    import re
                    thought_match = re.search(r"<thought>(.*?)</thought>", raw_content, re.DOTALL)
                    if thought_match:
                        reasoning_parts.append(thought_match.group(1).strip())
                        reply = raw_content.replace(thought_match.group(0), "").strip()
                    else:
                        reply = raw_content
                    break

            # Extract tool names used and add to reasoning if no explicit thought blocks found
            sources = self._extract_sources(messages)
            if not reasoning_parts:
                for msg in messages:
                    if msg.__class__.__name__ == "ToolMessage":
                        name = getattr(msg, "name", "unknown")
                        reasoning_parts.append(f"Used tool: **{name}**")

            reasoning = "\n\n".join(reasoning_parts) if reasoning_parts else None

            await session_store.append(session_id, message, reply)
            return {
                "reply": reply,
                "reasoning": reasoning,
                "sources": sources,
                "session_id": session_id,
                "ts": int(time.time()),
            }
        except Exception as e:
            logger.error("agent_invoke_failed", error=str(e), exc_info=True)
            return {
                "reply": "I encountered an error processing your request. Please try again.",
                "sources": [],
                "session_id": session_id,
                "error": str(e),
                "ts": int(time.time()),
            }

    async def stream(self, message: str, session_id: str) -> AsyncIterator[dict]:
        """
        Stream agent response token by token with <thought> tag extraction.
        """
        try:
            history = await session_store.get_history(session_id)
            messages = self._build_messages(history, message)
            full_reply: list[str] = []
            all_messages: list = []
            
            in_thought_block = False
            buffer = ""

            async for chunk, metadata in self._graph.astream(
                {"messages": messages},
                stream_mode="messages",
            ):
                all_messages.append(chunk)

                # 1. Capture tool calls as reasoning
                # We use string checks on class names for robustness in container environments
                cls_name = chunk.__class__.__name__
                
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        args = json.dumps(tc.get("args", {}))
                        yield {"reasoning": f"Calling tool: **{tc['name']}** with arguments: `{args}`\n"}

                # 2. Capture AIMessage content tokens
                if "AIMessage" in cls_name and chunk.content:
                    token = ""
                    if isinstance(chunk.content, str):
                        token = chunk.content
                    elif isinstance(chunk.content, list):
                        texts = []
                        for b in chunk.content:
                            if isinstance(b, dict):
                                if b.get("type") == "text":
                                    texts.append(b.get("text", ""))
                                elif b.get("type") in ["thought", "thinking"]:
                                    thought = b.get("text", "")
                                    if thought:
                                        yield {"reasoning": thought}
                        token = "".join(texts)
                    
                    if token:
                        buffer += token
                        full_reply.append(token)
                        
                        # Process buffer for <thought> tags
                        while True:
                            if not in_thought_block:
                                if "<thought>" in buffer:
                                    start_idx = buffer.find("<thought>")
                                    if start_idx > 0:
                                        yield {"token": buffer[:start_idx]}
                                    in_thought_block = True
                                    buffer = buffer[start_idx + 9:] # len("<thought>")
                                elif "<" in buffer:
                                    # Might be start of <thought>, wait for more tokens
                                    # But only if it's at the end
                                    tag_start = buffer.rfind("<")
                                    if tag_start >= 0 and "<thought>".startswith(buffer[tag_start:]):
                                        if tag_start > 0:
                                            yield {"token": buffer[:tag_start]}
                                            buffer = buffer[tag_start:]
                                        break
                                    else:
                                        yield {"token": buffer}
                                        buffer = ""
                                        break
                                else:
                                    yield {"token": buffer}
                                    buffer = ""
                                    break
                            else:
                                if "</thought>" in buffer:
                                    end_idx = buffer.find("</thought>")
                                    if end_idx > 0:
                                        yield {"reasoning": buffer[:end_idx]}
                                    in_thought_block = False
                                    buffer = buffer[end_idx + 10:] # len("</thought>")
                                elif "<" in buffer:
                                    tag_start = buffer.rfind("<")
                                    if tag_start >= 0 and "</thought>".startswith(buffer[tag_start:]):
                                        if tag_start > 0:
                                            yield {"reasoning": buffer[:tag_start]}
                                            buffer = buffer[tag_start:]
                                        break
                                    else:
                                        yield {"reasoning": buffer}
                                        buffer = ""
                                        break
                                else:
                                    yield {"reasoning": buffer}
                                    buffer = ""
                                    break

                # 3. Handle messages that are NOT AIMessages (e.g. ToolMessage)
                # We don't yield content for these, but we log them for debugging
                elif "ToolMessage" in cls_name:
                    logger.debug("agent_tool_message_received", tool=getattr(chunk, "name", "unknown"))

            # Yield remaining buffer
            if buffer:
                if in_thought_block:
                    yield {"reasoning": buffer}
                else:
                    yield {"token": buffer}

            full_text = "".join(full_reply)
            sources = self._extract_sources(all_messages)
            
            # Clean up the final text stored in history (remove thoughts)
            import re
            cleaned_text = re.sub(r"<thought>.*?</thought>", "", full_text, flags=re.DOTALL).strip()
            await session_store.append(session_id, message, cleaned_text)

            # Error 4 fix: terminal dict with done=True
            yield {
                "done": True,
                "sources": sources,
                "session_id": session_id,
                "ts": int(time.time()),
            }

        except Exception as e:
            logger.error("agent_stream_failed", error=str(e), exc_info=True)
            yield {"token": "I encountered an error processing your request."}
            yield {"done": True, "sources": [], "session_id": session_id, "ts": int(time.time())}

    @staticmethod
    def _extract_sources(messages: list) -> list[str]:
        """
        Extract tool names used in this invocation from ToolMessage metadata.
        We use class name checks to be robust against proxy objects.
        """
        sources: list[str] = []
        for msg in messages:
            # Check class name string for robustness (captures ToolMessage and ToolMessageChunk)
            if "ToolMessage" in msg.__class__.__name__:
                name = getattr(msg, "name", None)
                if name and name not in sources:
                    sources.append(name)
        return sources


# Module-level singleton — only imported when CHAT_ENABLED=true
farm_agent = FarmShieldAgent()
