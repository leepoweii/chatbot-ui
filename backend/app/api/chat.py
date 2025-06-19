from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from core.llm_client_anthropic import LLMClient
from db.models import Message, Session, UserStats
from db.engine import engine
from sqlmodel import Session as DBSession
import time
import json
import logging

# 設置詳細日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_serialize(obj, debug=False):
    """安全地序列化物件，處理 Anthropic SDK 的特殊物件"""
    if debug:
        print(f"Serializing object of type: {type(obj)}")
        if hasattr(obj, '__dict__'):
            print(f"Object attributes: {list(obj.__dict__.keys())}")
    
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize(item, debug) for item in obj]
    elif isinstance(obj, dict):
        return {k: safe_serialize(v, debug) for k, v in obj.items()}
    elif hasattr(obj, 'model_dump'):
        # Pydantic 模型
        return safe_serialize(obj.model_dump(), debug)
    elif hasattr(obj, '__dict__'):
        # 其他物件，轉換為字典
        return safe_serialize(obj.__dict__, debug)
    else:
        # 無法序列化的物件，轉為字串
        return str(obj)

router = APIRouter()
llm = LLMClient()

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: Optional[List[dict]] = None
    model: Optional[str] = "claude-sonnet-4-20250514"

@router.post("/chat")
def chat_endpoint(req: ChatRequest):
    logger.info(f"[CHAT] 收到同步請求: session_id={req.session_id}, message='{req.message}'")
    # 同步版本：完整 JSON 回應，用於不支援 streaming 的情況
    now = int(time.time() * 1000)
    with DBSession(engine) as db:
        user_msg = Message(
            session_id=req.session_id,
            role="user",
            content=req.message,
            timestamp_ms=now
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # 準備完整 session 歷史訊息
        if req.history is not None:
            messages = req.history
            messages.append({"role": "user", "content": req.message})
        else:
            # 從資料庫獲取所有訊息（包括剛剛存儲的用戶訊息）
            db_msgs = db.query(Message).filter(Message.session_id == req.session_id).order_by(Message.timestamp_ms).all()
            messages = [{"role": m.role, "content": m.content} for m in db_msgs]
            # 不需要再次添加用戶訊息，因為已經在資料庫中了
        
        # 使用同步 chat 方法獲取完整回應
        llm_resp = llm.chat(messages, model=req.model)

        # 存 assistant message
        assistant_msg = Message(
            session_id=req.session_id,
            role="assistant",
            content=llm_resp["content"],
            timestamp_ms=int(time.time() * 1000),
            tool_calls_json=str(llm_resp.get("tool_calls", [])),
            prompt_tokens=llm_resp.get("prompt_tokens"),
            completion_tokens=llm_resp.get("completion_tokens"),
            total_tokens=llm_resp.get("total_tokens")
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        # Session 累加 token
        session = db.get(Session, req.session_id)
        if session:
            session.prompt_tokens += llm_resp.get("prompt_tokens") or 0
            session.completion_tokens += llm_resp.get("completion_tokens") or 0
            session.total_tokens += llm_resp.get("total_tokens") or 0
            db.add(session)
            db.commit()

        # UserStats 累加 token
        user_stats = db.get(UserStats, 1)
        if not user_stats:
            user_stats = UserStats(id=1)
        user_stats.prompt_tokens += llm_resp.get("prompt_tokens") or 0
        user_stats.completion_tokens += llm_resp.get("completion_tokens") or 0
        user_stats.total_tokens += llm_resp.get("total_tokens") or 0
        db.add(user_stats)
        db.commit()

        return {
            "message": assistant_msg.content,
            "tool_calls": llm_resp.get("tool_calls", []),
            "prompt_tokens": llm_resp.get("prompt_tokens"),
            "completion_tokens": llm_resp.get("completion_tokens"),
            "total_tokens": llm_resp.get("total_tokens")
        }

@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    logger.info(f"[CHAT_STREAM] 收到 streaming 請求: session_id={req.session_id}, message='{req.message}'")
    # Streaming 版本：SSE + JSON，用於支援 streaming UI
    
    # 1. 先存 user message
    now = int(time.time() * 1000)
    with DBSession(engine) as db:
        user_msg = Message(
            session_id=req.session_id,
            role="user",
            content=req.message,
            timestamp_ms=now
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # 2. 準備歷史訊息
        if req.history is not None:
            messages = req.history
            messages.append({"role": "user", "content": req.message})
        else:
            # 從資料庫獲取所有訊息（包括剛剛存儲的用戶訊息）
            db_msgs = db.query(Message).filter(Message.session_id == req.session_id).order_by(Message.timestamp_ms).all()
            messages = [{"role": m.role, "content": m.content} for m in db_msgs]
            # 不需要再次添加用戶訊息，因為已經在資料庫中了

    # 3. Streaming 回應 + 同時收集完整內容用於存儲
    def event_stream():
        collected_content = ""
        collected_tokens = {"prompt": 0, "completion": 0, "total": 0}
        assistant_msg_id = None
        tool_calls = []
        
        # 發送開始事件
        yield f"data: {json.dumps({'type': 'start', 'session_id': req.session_id})}\n\n"
        
        try:
            # 流式獲取回應（支援 MCP 事件）
            for event in llm.chat_stream(messages, model=req.model):
                if event["type"] == "text":
                    collected_content += event["content"]
                    chunk_data = {
                        "type": "chunk",
                        "content": event["content"],
                        "session_id": req.session_id
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                elif event["type"] == "mcp_tool_use":
                    # 使用 safe_serialize 處理可能的 BetaTextBlock 物件
                    tool_call_data = {
                        "type": "tool_use",
                        "name": safe_serialize(event.get("name", "")),
                        "server_name": safe_serialize(event.get("server_name", "")),
                        "input": safe_serialize(event.get("input", {})),
                        "session_id": req.session_id
                    }
                    
                    tool_calls.append({
                        "name": safe_serialize(event.get("name", "")),
                        "input": safe_serialize(event.get("input", {}))
                    })
                    yield f"data: {json.dumps(tool_call_data)}\n\n"
                    
                elif event["type"] == "mcp_tool_result":
                    tool_result_data = {
                        "type": "tool_result",
                        "content": safe_serialize(event.get("content", "")),
                        "is_error": bool(event.get("is_error", False)),
                        "session_id": req.session_id
                    }
                    yield f"data: {json.dumps(tool_result_data)}\n\n"
            
            # Token 估算（MCP 調用可能影響 token 消耗）
            collected_tokens = {
                "prompt": len(' '.join([m.get('content', '') for m in messages])) // 4,  # 粗略估算
                "completion": len(collected_content) // 4,  # 粗略估算
                "total": 0
            }
            collected_tokens["total"] = collected_tokens["prompt"] + collected_tokens["completion"]
            
        except Exception as e:
            import traceback
            print(f"ERROR in event_stream: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            error_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"
            return
        
        # 4. 存儲完整的 assistant message 到資料庫
        with DBSession(engine) as db:
            # 使用 safe_serialize 處理 tool_calls
            safe_tool_calls = safe_serialize(tool_calls) if tool_calls else []
            tool_calls_json = json.dumps(safe_tool_calls)
            
            assistant_msg = Message(
                session_id=req.session_id,
                role="assistant", 
                content=collected_content,
                timestamp_ms=int(time.time() * 1000),
                tool_calls_json=tool_calls_json,
                prompt_tokens=collected_tokens["prompt"],
                completion_tokens=collected_tokens["completion"],
                total_tokens=collected_tokens["total"]
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)
            
            # 在 session 內取得 ID，避免 DetachedInstanceError
            assistant_msg_id = assistant_msg.id

            # 更新 session tokens
            session = db.get(Session, req.session_id)
            if session:
                session.prompt_tokens += collected_tokens["prompt"]
                session.completion_tokens += collected_tokens["completion"] 
                session.total_tokens += collected_tokens["total"]
                db.add(session)
                db.commit()

            # 更新 user stats
            user_stats = db.get(UserStats, 1)
            if not user_stats:
                user_stats = UserStats(id=1)
            user_stats.prompt_tokens += collected_tokens["prompt"]
            user_stats.completion_tokens += collected_tokens["completion"]
            user_stats.total_tokens += collected_tokens["total"]
            db.add(user_stats)
            db.commit()

        # 5. 發送結束事件，包含完整 metadata
        end_data = {
            "type": "end",
            "session_id": req.session_id,
            "message_id": assistant_msg_id,
            "prompt_tokens": collected_tokens["prompt"],
            "completion_tokens": collected_tokens["completion"],
            "total_tokens": collected_tokens["total"]
        }
        yield f"data: {json.dumps(end_data)}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
