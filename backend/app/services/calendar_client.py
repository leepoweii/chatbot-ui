import os
import requests

MCP_BASE_URL = os.getenv("MCP_BASE_URL", "")

class CalendarClient:
    def list_gcal_events(self, payload: dict) -> dict:
        url = f"{MCP_BASE_URL}/mcp/calendar/list_gcal_events"
        resp = requests.post(url, json=payload)
        return resp.json()

    def create_event(self, payload: dict) -> dict:
        url = f"{MCP_BASE_URL}/mcp/calendar/create_event"
        resp = requests.post(url, json=payload)
        return resp.json()
