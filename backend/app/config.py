from dotenv import load_dotenv
import os

load_dotenv()

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "你是一個高效的 AI 助理，請用繁體中文回覆。")
OPENAI_KEY = os.getenv("OPENAI_KEY", "")
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "")
