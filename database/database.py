"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database file
SQLALCHEMY_DATABASE_URL = "sqlite:///./viralcutter.db"

# Create engine with check_same_thread=False for SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    """
    Dependency function to get database session.
    Usage in FastAPI endpoints:
        def endpoint(db: Session = Depends(get_db)):
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize database tables.
    Call this once at application startup.
    """
    from . import models  # Import models to register them
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")
