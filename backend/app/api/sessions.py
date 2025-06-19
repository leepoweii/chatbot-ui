from fastapi import APIRouter, HTTPException
from sqlmodel import Session as DBSession, select, SQLModel
from db.models import Session as SessionModel, Message as MessageModel
from db.engine import engine
from typing import List

router = APIRouter()

# Initialize database tables if they don't exist
def ensure_db_initialized():
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f"Database initialization warning: {e}")

@router.post("/sessions")
def create_session(session: SessionModel):
    ensure_db_initialized()
    with DBSession(engine) as db:
        db.add(session)
        db.commit()
        db.refresh(session)
        return {"data": session.dict()}

@router.get("/sessions", response_model=List[SessionModel])
def list_sessions():
    ensure_db_initialized()
    with DBSession(engine) as db:
        sessions = db.exec(select(SessionModel)).all()
        return sessions

@router.get("/sessions/{session_id}/history")
def get_session_history(session_id: str):
    with DBSession(engine) as db:
        messages = db.exec(select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.timestamp_ms)).all()
        return {"data": messages}

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    with DBSession(engine) as db:
        session = db.get(SessionModel, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        db.delete(session)
        db.commit()
        return {"ok": True}
