import os
import requests

MCP_BASE_URL = os.getenv("MCP_BASE_URL", "")

class TodoistClient:
    def post_sse(self, payload: dict) -> dict:
        url = f"{MCP_BASE_URL}/mcp/todoist/sse"
        resp = requests.post(url, json=payload)
        return resp.json()

    def get_tasks(self, payload: dict) -> dict:
        # 轉為 post_sse，action/type 由 LLM 傳入
        return self.post_sse(payload)

    def create_task(self, payload: dict) -> dict:
        # 轉為 post_sse，action/type 由 LLM 傳入
        return self.post_sse(payload)
