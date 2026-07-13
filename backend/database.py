import os
import platform
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load the backend .env so SECRET_KEY / NOC360_* env vars are honoured. The
# systemd unit does not set an EnvironmentFile and uvicorn is started without
# --env-file, so without this the app silently falls back to insecure defaults
# (e.g. the default JWT SECRET_KEY, which would allow token forgery).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "noc360.db" if platform.system() == "Windows" else Path("/opt/noc360/backend/noc360.db")
DATABASE_PATH = Path(os.getenv("NOC360_DATABASE_PATH", DEFAULT_DATABASE_PATH))
DB_PROTECTED_MARKER = DATABASE_PATH.parent / ".db_protected"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_PROTECTED_MARKER.touch(exist_ok=True)
print(f"Using database: {DATABASE_PATH}", flush=True)

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
