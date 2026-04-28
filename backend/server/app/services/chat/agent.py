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

SYSTEM_PROMPT = """You are FarmShield Assistant — an AI embedded in a smart agriculture \
monitoring system deployed on a real farm.

You have access to three tools:
- sql_database_schema (InfoSQLDatabaseTool): use this to inspect table schemas before writing SQL.
- sql_database_query (QuerySQLDataBaseTool): use this to run SQL queries against live sensor data.
- search_farming_knowledge: use for general questions about crop care, soil science, irrigation, \
NPK nutrients, pH ranges, and pest management.

Rules:
1. ALWAYS start your response with your internal thought process wrapped in `<thought>` tags.
   Example: `<thought>The user is asking for moisture data. I need to query the database.</thought>`
2. Always think step by step before using any tool. Explain your plan clearly in the thought block.
2. Always use the SQL query tool before making any claim about current or historical sensor values.
3. Never invent or guess sensor readings. If a query returns no rows, say so clearly.
4. Use sql_database_schema first if you are unsure of column names or data types.
5. Keep answers concise and actionable. Farmers want facts and clear next steps, not essays.
6. If a question is completely unrelated to agriculture or this farm, politely decline.
7. If the user does not specify a device, you MUST look up the available device_ids in the sensor_readings table first (e.g. SELECT DISTINCT device_id FROM sensor_readings). Do NOT use {device_id} to query sensor data, as that is the backend server's ID.
8. The sensor_readings table contains: time (TIMESTAMP WITH TIME ZONE), device_id (TEXT), soil_pct, ph, tds_ppm, temp_c, humidity_pct, rain_raw, motion (BOOLEAN), npk_n, npk_p, npk_k, leaf_r, leaf_g, leaf_b, pump_on (BOOLEAN), mode (TEXT), uptime_s, npk_ok (BOOLEAN).
9. The alerts table contains: id, time, device_id, alert_type, severity, value, threshold, message.
10. You are a highly capable multilingual assistant. You MUST detect and respond in the EXACT same language used by the user in their most recent message. If the user switches from one language to another, you must switch to that language immediately. Do not be biased by previous language history.
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
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        args = json.dumps(tc.get("args", {}))
                        yield {"reasoning": f"Calling tool: **{tc['name']}** with arguments: `{args}`\n"}

                # 2. Capture AIMessage content tokens
                if isinstance(chunk, AIMessage) and chunk.content:
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
        Each ToolMessage has a `name` attribute indicating which tool was called.
        """
        from langchain_core.messages import ToolMessage
        sources: list[str] = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                name = getattr(msg, "name", None)
                if name and name not in sources:
                    sources.append(name)
        return sources


# Module-level singleton — only imported when CHAT_ENABLED=true
farm_agent = FarmShieldAgent()
