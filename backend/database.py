from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_PATH = Path("/opt/noc360/backend/noc360.db")
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
