"""
FarmShield Backend — Application Entry Point.

Creates the FastAPI app with lifespan context manager.
Startup sequence follows PRD §19 exactly:
  1. Configure logging
  2. Validate env vars (pydantic-settings does this on Settings() instantiation)
  3. Test DB connection (SELECT 1)
  4. Apply retention policy if RETENTION_DAYS > 0
  5. Load ML model if ML_ENABLED=true
  6. Start MQTT client
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal, async_engine

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App lifespan — governs startup and shutdown sequence.
    Follows PRD §19 ordering.
    """
    # ── 1. Configure logging (before anything else logs) ────────────────
    configure_logging(settings.log_level, settings.log_json)
    logger.info("startup_begin", target_env=settings.target_env)

    # ── 2. Settings validation happened at import time (config.py) ──────
    # pydantic-settings raises if required vars are missing.

    # ── 3. Test DB connection ───────────────────────────────────────────
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("db_connection_verified")
    except Exception as e:
        logger.error("db_connection_failed", error=str(e), exc_info=True)
        raise

    # ── 4. Apply retention policy if configured ─────────────────────────
    if settings.retention_days > 0:
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text(
                        f"SELECT add_retention_policy('sensor_readings', "
                        f"INTERVAL '{settings.retention_days} days', "
                        f"if_not_exists => TRUE)"
                    )
                )
                await session.commit()
            logger.info("retention_policy_applied", days=settings.retention_days)
        except Exception as e:
            logger.error("retention_policy_failed", error=str(e), exc_info=True)
            raise

    # ── 5. Load ML model if enabled ─────────────────────────────────────
    if settings.ml_enabled:
        from app.services.ml.runner import MLRunner

        ml_runner = MLRunner()
        ml_runner.load()  # Raises FileNotFoundError if model missing

        from app.services import ingestion

        ingestion.set_ml_runner(ml_runner)
        logger.info("ml_runner_loaded", model_type=settings.ml_model_type)

    # ── 5b. Load chat feature if enabled ────────────────────────────────
    if settings.chat_enabled:
        from app.services.chat.rag_tool import RagTool
        from app.services.chat.sql_tool import build_sql_tools
        from app.services.chat.agent import farm_agent

        logger.info("chat_startup_begin")
        rag = RagTool()
        await rag.load_or_build_index(settings)   # may take 10–30 s on first run
        sql_tools = build_sql_tools(settings)
        farm_agent.load(sql_tools, rag.get_tool(), settings)

        from app.api.v1 import health as health_module
        health_module.set_chat_ready(True)
        logger.info("chat_startup_complete")

    # ── 6. Start MQTT client ────────────────────────────────────────────
    from app.mqtt.client import fast_mqtt

    # Import handlers to register decorators (side-effect import)
    import app.mqtt.handlers  # noqa: F401

    # Inject MQTT client into services that need it
    from app.api.v1 import health as health_module
    from app.services import alert as alert_service
    from app.services import control as control_service

    health_module.set_mqtt_client(fast_mqtt)
    control_service.set_mqtt_client(fast_mqtt)
    alert_service.set_mqtt_client(fast_mqtt)

    await fast_mqtt.mqtt_startup()
    logger.info(
        "mqtt_client_started",
        broker=f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
    )

    logger.info("startup_complete")

    yield

    # ── Shutdown ────────────────────────────────────────────────────────
    logger.info("shutdown_begin")
    await fast_mqtt.mqtt_shutdown()
    await async_engine.dispose()
    logger.info("shutdown_complete")


# ── App factory ─────────────────────────────────────────────────────────
app = FastAPI(
    title="FarmShield Backend",
    description="Edge-AI smart agriculture backend — REST + WebSocket API",
    version="1.0.0",
    lifespan=lifespan,
)

# Register exception handlers (PRD §16)
register_exception_handlers(app)

# Include API router
app.include_router(api_v1_router)

# ── CORS Middleware ──────────────────────────────────────────────────────
# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Root Health Redirect ──────────────────────────────────────────────────
# Redirect /health to /api/v1/health to match frontend expectations
@app.get("/health", include_in_schema=False)
async def health_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/v1/health")
