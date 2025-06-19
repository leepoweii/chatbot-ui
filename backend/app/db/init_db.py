from sqlmodel import SQLModel
import logging
import sys
import os

# Add the parent directory to the path so we can import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try relative import first
    from .models import Session, Message, UserStats
    from .engine import engine
except ImportError:
    # Fall back to absolute import when run as script
    from db.models import Session, Message, UserStats
    from db.engine import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    try:
        logger.info("Creating database tables...")
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

if __name__ == "__main__":
    init_db()
