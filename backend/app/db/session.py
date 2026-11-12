import atexit
from contextlib import contextmanager
from typing import Generator, Optional
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings

_pg_server_instance = None
_engine = None
_SessionLocal = None


def _resolve_database_url() -> str:
    global _pg_server_instance
    settings = get_settings()
    if settings.DATABASE_URL:
        return settings.DATABASE_URL

    # Local dev fallback: boot an isolated local PostgreSQL process via pgserver
    import pgserver

    if _pg_server_instance is None:
        _pg_server_instance = pgserver.get_server(settings.PGSERVER_DATA_DIR)
        atexit.register(stop_embedded_pgserver)

    raw_uri = _pg_server_instance.get_uri()
    # Convert postgresql:// to SQLAlchemy psycopg3 driver DSN
    if raw_uri.startswith("postgresql://"):
        return raw_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if raw_uri.startswith("postgres://"):
        return raw_uri.replace("postgres://", "postgresql+psycopg://", 1)
    return raw_uri


def stop_embedded_pgserver() -> None:
    global _pg_server_instance
    if _pg_server_instance is not None:
        try:
            _pg_server_instance.cleanup()
        except Exception:
            pass
        _pg_server_instance = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        dsn = _resolve_database_url()
        _engine = create_engine(
            dsn,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=10,
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory():
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal


def apply_tenant_rls(db: Session, tenant_id: uuid.UUID) -> None:
    """
    Bind PostgreSQL transaction-local RLS role & tenant context.
    - SET LOCAL ROLE rent_agent_app ensures non-superuser RLS enforcement even when
      the connection pool authenticates as the table owner/superuser.
    - set_config(..., is_local=true) prevents leakage across pooled connections.
    """
    db.execute(text("SET LOCAL ROLE rent_agent_app"))
    db.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def get_db() -> Generator[Session, None, None]:
    """Raw control-plane DB session (used for auth lookup, global catalog, and registration)."""
    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def tenant_scoped_session(tenant_id: uuid.UUID) -> Generator[Session, None, None]:
    """Context manager enforcing PostgreSQL RLS inside an explicit transaction."""
    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        apply_tenant_rls(db, tenant_id)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
