import os
from dotenv import load_dotenv
import anthropic
import json

load_dotenv()

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.md")
with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# 載入 MCP servers 設定
MCP_SERVERS_PATH = os.path.join(os.path.dirname(__file__), "mcp_servers.json")
if os.path.exists(MCP_SERVERS_PATH):
    with open(MCP_SERVERS_PATH, "r", encoding="utf-8") as f:
        MCP_SERVERS = json.load(f)
else:
    MCP_SERVERS = []

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

class LLMClient:
    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.mcp_servers = MCP_SERVERS

    def chat(self, messages: list, model: str = None, mcp_servers: list = None) -> dict:
        # Build messages for Anthropic API
        system_prompt = None
        anthropic_messages = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            elif m["role"] in ("user", "assistant"):
                anthropic_messages.append({"role": m["role"], "content": m["content"]})
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        model_name = model or self.model
        api_kwargs = dict(
            model=model_name,
            max_tokens=1024,
            temperature=0.7,
            messages=anthropic_messages
        )
        if system_prompt:
            api_kwargs["system"] = system_prompt
        
        # 加入 MCP Connector 支援
        servers_to_use = mcp_servers or self.mcp_servers
        if servers_to_use:
            api_kwargs.update({
                "mcp_servers": servers_to_use,
                "betas": ["mcp-client-2025-04-04"]
            })
            response = self.client.beta.messages.create(**api_kwargs)
        else:
            response = self.client.messages.create(**api_kwargs)
        
        usage = getattr(response, 'usage', None)
        # Parse content blocks - 支援 MCP 工具回應
        content = ""
        tool_calls = []
        if hasattr(response, 'content') and isinstance(response.content, list):
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "mcp_tool_use":
                    tool_calls.append({
                        "type": "mcp_tool_use",
                        "name": safe_serialize(getattr(block, 'name', '')),
                        "server_name": safe_serialize(getattr(block, 'server_name', '')),
                        "input": safe_serialize(getattr(block, 'input', {}))
                    })
                elif block.type == "mcp_tool_result":
                    # 工具結果通常會包含在內容中，這裡記錄但不改變主要回應
                    pass
        elif hasattr(response, 'content'):
            content = response.content
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
            "prompt_tokens": usage.input_tokens if usage else None,
            "completion_tokens": usage.output_tokens if usage else None,
            "total_tokens": (usage.input_tokens + usage.output_tokens) if usage else None
        }

    def chat_stream(self, messages: list, model: str = None, mcp_servers: list = None):
        """Streaming chat response with MCP Connector support"""
        # 建構訊息（與 chat() 相同邏輯）
        system_prompt = None
        anthropic_messages = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            elif m["role"] in ("user", "assistant"):
                anthropic_messages.append({"role": m["role"], "content": m["content"]})
        
        if not system_prompt:
            system_prompt = SYSTEM_PROMPT
        
        model_name = model or self.model
        
        # 支援 MCP + Streaming
        servers_to_use = mcp_servers or self.mcp_servers
        
        stream_kwargs = dict(
            model=model_name,
            max_tokens=1024,
            temperature=0.7,
            messages=anthropic_messages
        )
        if system_prompt:
            stream_kwargs["system"] = system_prompt
        
        if servers_to_use:
            # 使用 MCP Connector + Streaming
            stream_kwargs.update({
                "mcp_servers": servers_to_use,
                "betas": ["mcp-client-2025-04-04"]
            })
            with self.client.beta.messages.stream(**stream_kwargs) as stream:
                for event in stream:
                    # 處理文字增量
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, 'text'):
                            yield {
                                "type": "text",
                                "content": event.delta.text
                            }
                    # 處理 content block 開始事件
                    elif event.type == "content_block_start":
                        if hasattr(event.content_block, 'type'):
                            # 處理 MCP 工具使用
                            if event.content_block.type == "mcp_tool_use":
                                yield {
                                    "type": "mcp_tool_use",
                                    "name": safe_serialize(getattr(event.content_block, 'name', '')),
                                    "server_name": safe_serialize(getattr(event.content_block, 'server_name', '')),
                                    "input": safe_serialize(getattr(event.content_block, 'input', {}))
                                }
                    # 處理 content block 停止事件
                    elif event.type == "content_block_stop":
                        if hasattr(event, 'content_block') and hasattr(event.content_block, 'type'):
                            # 處理 MCP 工具結果
                            if event.content_block.type == "mcp_tool_result":
                                # 安全地處理 content 列表
                                content_items = getattr(event.content_block, 'content', [])
                                processed_content = ""
                                
                                if isinstance(content_items, list):
                                    for item in content_items:
                                        if hasattr(item, 'text'):
                                            processed_content += str(item.text)
                                        elif hasattr(item, 'type') and item.type == 'text':
                                            processed_content += str(getattr(item, 'text', ''))
                                        else:
                                            processed_content += str(safe_serialize(item))
                                else:
                                    processed_content = str(safe_serialize(content_items))
                                    
                                yield {
                                    "type": "mcp_tool_result",
                                    "content": processed_content,
                                    "is_error": getattr(event.content_block, 'is_error', False)
                                }
        else:
            # 原本的純 streaming 邏輯（無 MCP）
            with self.client.messages.stream(**stream_kwargs) as stream:
                for text in stream.text_stream:
                    yield {"type": "text", "content": text}
