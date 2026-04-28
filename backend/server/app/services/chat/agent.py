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
1. Always use the SQL query tool before making any claim about current or historical sensor values.
2. Never invent or guess sensor readings. If a query returns no rows, say so clearly.
3. Use sql_database_schema first if you are unsure of column names or data types.
4. Keep answers concise and actionable. Farmers want facts and clear next steps, not essays.
5. If a question is completely unrelated to agriculture or this farm, politely decline.
6. Default device_id for all queries: {device_id}
7. The sensor_readings table contains: time, device_id, soil_pct, temperature_c, humidity_pct, \
ph, tds_ppm, rain_raw, nitrogen_mgkg, phosphorus_mgkg, potassium_mgkg, leaf_color, pump_state.
8. The alerts table contains: id, time, device_id, alert_type, severity, value, threshold, message.
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
        Called once during app lifespan startup when CHAT_ENABLED=true.

        Uses langchain.agents.create_agent (LangChain 1.2.x) which builds a
        LangGraph CompiledStateGraph. The graph uses Gemini's native function
        calling — no text-based ReAct prompting needed.

        Args:
            sql_tools: [InfoSQLDatabaseTool, QuerySQLDataBaseTool]
            rag_tool: search_farming_knowledge tool
            settings: app settings instance
        """
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.chat_temperature,
            max_output_tokens=settings.chat_max_output_tokens,
        )

        # Error 3 fix: device_id from settings, not hardcoded
        self._system_message = SYSTEM_PROMPT.format(device_id=settings.mqtt_client_id)

        tools = sql_tools + [rag_tool]  # [InfoSQL, QuerySQL, search_farming_knowledge]

        # create_agent returns a CompiledStateGraph.
        # system_prompt is passed as a string — the graph prepends it as a SystemMessage.
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
            sources: list[str] = []
            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    if isinstance(msg.content, str):
                        reply = msg.content
                    elif isinstance(msg.content, list):
                        # Extract text blocks (e.g. ignoring 'thinking' blocks)
                        texts = [b.get("text", "") for b in msg.content if isinstance(b, dict) and b.get("type") == "text"]
                        reply = "\n".join(texts) if texts else str(msg.content)
                    else:
                        reply = str(msg.content)
                    break

            # Extract tool names used from intermediate ToolMessages
            sources = self._extract_sources(result.get("messages", []))

            await session_store.append(session_id, message, reply)
            return {
                "reply": reply,
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
        Stream agent response token by token.

        Error 4 fix: yields dicts instead of raw strings.
          - Regular tokens: {"token": "..."}
          - Final item:     {"done": True, "sources": [...], "session_id": "...", "ts": int}

        The SSE generator in chat.py checks for "done" key to route correctly.

        Note: LangGraph astream with stream_mode="messages" yields (message_chunk, metadata)
        tuples. We filter for AIMessage chunks from the model node.
        """
        try:
            history = await session_store.get_history(session_id)
            messages = self._build_messages(history, message)
            full_reply: list[str] = []
            all_messages: list = []

            async for chunk, metadata in self._graph.astream(
                {"messages": messages},
                stream_mode="messages",
            ):
                all_messages.append(chunk)
                # Only yield AIMessage content tokens (not tool results)
                if isinstance(chunk, AIMessage) and chunk.content:
                    if isinstance(chunk.content, str):
                        token = chunk.content
                    elif isinstance(chunk.content, list):
                        texts = [b.get("text", "") for b in chunk.content if isinstance(b, dict) and b.get("type") == "text"]
                        token = "".join(texts)
                    else:
                        token = str(chunk.content)

                    if token:
                        full_reply.append(token)
                        yield {"token": token}

            full_text = "".join(full_reply)
            sources = self._extract_sources(all_messages)
            await session_store.append(session_id, message, full_text)

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
