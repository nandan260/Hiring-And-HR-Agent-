from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .api.router import api_router
from .config import get_settings
from .db.seed import seed_initial_data
from .db.session import get_engine, get_session_factory, stop_embedded_pgserver


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    # Note: Schema tables must always be managed via Alembic (`alembic upgrade head`).
    # We never call Base.metadata.create_all() here.
    get_engine()
    if settings.AUTO_SEED_CATALOG:
        SessionFactory = get_session_factory()
        with SessionFactory() as db:
            try:
                db.execute(text("SELECT 1 FROM agent_catalog LIMIT 1"))
                seed_initial_data(db, include_demo_tenants=True)
            except SQLAlchemyError:
                db.rollback()
    yield
    stop_embedded_pgserver()


def create_app() -> FastAPI:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from sqlalchemy.exc import OperationalError, SQLAlchemyError

    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Multi-tenant Hiring & HR AI Agent Marketplace API with PostgreSQL FORCE RLS",
        lifespan=lifespan,
    )

    @app.exception_handler(OperationalError)
    async def handle_db_operational_error(_request: Request, _exc: OperationalError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Database service is temporarily unavailable. Please retry shortly.",
                "error_code": "database_unavailable",
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "A database processing error occurred. The operation was rolled back safely.",
                "error_code": "database_error",
            },
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System"])
    def health_check() -> dict:
        engine = get_engine()
        with engine.connect() as conn:
            pg_version = conn.execute(text("SELECT version()")).scalar_one()
        return {
            "status": "ok",
            "service": settings.APP_NAME,
            "database": "connected",
            "postgres_version": str(pg_version).split(",")[0],
        }

    app.include_router(api_router, prefix=settings.API_PREFIX)
    return app


app = create_app()
