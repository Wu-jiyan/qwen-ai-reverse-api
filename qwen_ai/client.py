"""Qwen AI Client - OpenAI compatible interface"""

from typing import List, Dict, Optional, Generator, Any
from .adapter import QwenAiAdapter
from .stream_handler import QwenAiStreamHandler
from .tool_parser import ToolParser

class QwenAiClient:
    """Qwen AI Client with OpenAI compatible interface"""

    def __init__(self, token: str, cookies: Optional[str] = None, use_proxy: bool = True):
        """Initialize Qwen AI Client

        Args:
            token: JWT token from chat.qwen.ai Local Storage
            cookies: Optional cookies string for enhanced compatibility
            use_proxy: Whether to use proxy (Vless or HTTP proxy)
        """
        self.adapter = QwenAiAdapter(token, cookies, use_proxy=use_proxy)
    
    def chat_completions(self, model: str, messages: List[Dict], stream: bool = False,
                        temperature: Optional[float] = None, tools: Optional[List[Dict]] = None,
                        enable_thinking: Optional[bool] = None, thinking_budget: Optional[int] = None,
                        auto_delete_chat: bool = False) -> Any:
        """Chat completions API

        Args:
            model: Model name
            messages: List of messages
            stream: Whether to use streaming
            temperature: Temperature setting
            tools: List of tools for function calling
            enable_thinking: Whether to enable thinking mode
            thinking_budget: Thinking budget
            auto_delete_chat: Whether to delete the chat after completion

        Returns:
            Generator for streaming, dict for non-streaming
        """
        processed_messages = messages.copy()
        if tools:
            has_tool_prompt = any(
                msg.get('role') == 'system' and
                ('Available Tools' in msg.get('content', '') or '<tools>' in msg.get('content', ''))
                for msg in messages
            )

            if not has_tool_prompt:
                tool_prompt = ToolParser.tools_to_system_prompt(tools)

                system_messages = [msg for msg in processed_messages if msg.get('role') == 'system']
                if system_messages:
                    system_messages[0]['content'] = system_messages[0]['content'] + '\n\n' + tool_prompt
                else:
                    processed_messages.insert(0, {'role': 'system', 'content': tool_prompt})

        response, chat_id, parent_id = self.adapter.chat_completion(
            model=model,
            messages=processed_messages,
            stream=stream,
            temperature=temperature,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            auto_delete_chat=auto_delete_chat
        )

        handler = QwenAiStreamHandler(
            model,
            auto_delete_chat=auto_delete_chat,
            delete_chat_func=self.adapter.delete_chat
        )
        handler.set_chat_id(chat_id)

        if stream:
            return handler.handle_stream(response)
        else:
            return handler.handle_non_stream(response)
    
    def create_chat(self, model: str, title: str = 'New Chat') -> str:
        """Create a new chat
        
        Args:
            model: Model name
            title: Chat title
        
        Returns:
            str: Chat ID
        """
        model_id = self.adapter.map_model(model)
        return self.adapter.create_chat(model_id, title)
    
    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat
        
        Args:
            chat_id: Chat ID
        
        Returns:
            bool: True if deletion was successful
        """
        return self.adapter.delete_chat(chat_id)
    
    def delete_all_chats(self) -> bool:
        """Delete all chats
        
        Returns:
            bool: True if deletion was successful
        """
        return self.adapter.delete_all_chats()
