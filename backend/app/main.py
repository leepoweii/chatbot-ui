from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.sessions import router as sessions_router
from api.chat import router as chat_router
from api.mcp import router as mcp_router
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Personal AI OS", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    try:
        logger.info("Initializing database on startup...")
        from db.init_db import init_db
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.warning("Continuing without database initialization")

app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(mcp_router)

@app.get("/health")
def health():
    return {"status": "ok", "message": "Personal AI OS is running"}

@app.get("/")
def root():
    return {"message": "Personal AI OS API", "status": "running"}
