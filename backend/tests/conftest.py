import os
from pathlib import Path
import shutil
import tempfile

from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest


@pytest.fixture(scope="session")
def test_environment():
    """
    Spin up an isolated temporary directory for embedded PostgreSQL 16 (pgserver)
    and tenant file uploads, run Alembic migrations, and seed catalog + demo tenants.
    """
    tmp_root = Path(tempfile.mkdtemp(prefix="rent_agent_pytest_"))
    pg_dir = tmp_root / "pgdata"
    upload_dir = tmp_root / "uploads"
    sandbox_dir = tmp_root / "sandboxes"
    browser_dir = tmp_root / "browsers"
    pg_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    browser_dir.mkdir(parents=True, exist_ok=True)

    os.environ["DATABASE_URL"] = ""
    os.environ["PGSERVER_DATA_DIR"] = str(pg_dir)
    os.environ["UPLOAD_ROOT"] = str(upload_dir)
    os.environ["SANDBOX_ROOT"] = str(sandbox_dir)
    os.environ["BROWSER_ROOT"] = str(browser_dir)
    os.environ["JWT_SECRET_KEY"] = "pytest-jwt-secret-key-at-least-32-chars-long"
    os.environ["CREDENTIALS_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")
    os.environ["AUTO_SEED_CATALOG"] = "false"

    from app.config import get_settings
    from app.db import session as db_session

    get_settings.cache_clear()
    db_session._engine = None
    db_session._SessionLocal = None
    db_session._pg_server_instance = None

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(alembic_cfg, "head")

    from app.db.seed import seed_initial_data

    SessionFactory = db_session.get_session_factory()
    with SessionFactory() as session:
        seed_initial_data(session, include_demo_tenants=True)

    yield {"tmp_root": tmp_root, "upload_dir": upload_dir}

    db_session.stop_embedded_pgserver()
    if db_session._engine is not None:
        db_session._engine.dispose()
    shutil.rmtree(tmp_root, ignore_errors=True)


@pytest.fixture(scope="session")
def client(test_environment):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
