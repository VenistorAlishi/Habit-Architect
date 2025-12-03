from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./habit_architect.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Initialize database tables."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator:
    """Provide a transactional scope for database operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
