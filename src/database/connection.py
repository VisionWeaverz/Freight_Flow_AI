"""Database connection engine and session factory."""

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker
    from src.common.config import DATABASE_URL

    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except ImportError:
    engine = None
    SessionLocal = None
    Base = object


def get_db():
    """Yields database session context."""
    if SessionLocal is None:
        raise RuntimeError("SQLAlchemy is required to create a database session. Please install requirements.txt.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
