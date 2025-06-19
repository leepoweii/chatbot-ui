from fastapi import APIRouter
from services.calendar_client import CalendarClient
from services.todoist_client import TodoistClient
from functools import wraps

router = APIRouter()
calendar_client = CalendarClient()
todoist_client = TodoistClient()

def mcp_unified_response(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            resp = func(*args, **kwargs)
            if resp.get("error"):
                return {"success": False, "error": resp["error"]}
            return {"success": True, "data": resp}
        except Exception as e:
            return {"success": False, "error": {"type": "Exception", "message": str(e)}}
    return wrapper

@router.post("/mcp/calendar/list_gcal_events")
@mcp_unified_response
def list_gcal_events(payload: dict):
    return calendar_client.list_gcal_events(payload)

@router.post("/mcp/calendar/create_event")
@mcp_unified_response
def create_event(payload: dict):
    return calendar_client.create_event(payload)

@router.post("/mcp/todoist/get_tasks")
@mcp_unified_response
def get_tasks(payload: dict):
    return todoist_client.get_tasks(payload)

@router.post("/mcp/todoist/create_task")
@mcp_unified_response
def create_task(payload: dict):
    return todoist_client.create_task(payload)
