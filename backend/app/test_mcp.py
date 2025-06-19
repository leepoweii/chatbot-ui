#!/usr/bin/env python3
"""
簡單的 MCP 測試腳本
"""
import json
import sys
import os
sys.path.insert(0, '/app')

from core.llm_client_anthropic import LLMClient

def test_mcp_streaming():
    """測試 MCP streaming"""
    client = LLMClient()
    print(f"MCP servers loaded: {len(client.mcp_servers)}")
    
    messages = [
        {"role": "user", "content": "Please check my calendar for today"}
    ]
    
    print("Starting stream...")
    try:
        for i, event in enumerate(client.chat_stream(messages)):
            print(f"Event {i}: type={event['type']}")
            
            # 測試序列化
            try:
                serialized = json.dumps(event)
                print(f"  Successfully serialized: {len(serialized)} chars")
            except Exception as e:
                print(f"  Serialization error: {e}")
                print(f"  Event data: {event}")
                
            if i > 10:  # 限制事件數量
                break
                
    except Exception as e:
        print(f"Stream error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mcp_streaming()
