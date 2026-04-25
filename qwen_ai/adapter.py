"""Qwen AI Adapter for chat.qwen.ai - Based on Chat2API logic"""

import json
import uuid
import time
import os
import requests
from typing import Dict, Optional, Tuple, Any

from .proxy_adapter import ProxyManager, get_proxy_manager, init_proxy_manager


class QwenAiAdapter:
    """Qwen AI Adapter for chat.qwen.ai"""
    
    QWEN_AI_BASE = 'https://chat.qwen.ai'
    
    DEFAULT_HEADERS = {
        'Accept': 'application/json',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Content-Type': 'application/json',
        'source': 'web',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'bx-v': '2.5.36',
        'bx-umidtoken': 'T2gAr9z8byN8sNOmfQ3X9j61MNTNmSqDO5L1rs2jMcQCVhOKgZICcBN-UdTuJGig-NM=',
        'bx-ua': '231!lWD36kmUe5E+joKDK5gBZ48FEl2ZWfPwIPF92lBLek2KxVW/XJ2EwruCiDOX5Px4EXNhmh6EfS9eDwQGRwijIK64A4nPqeLysJcDjUACje/H3J4ZgGZpicG6K8AkiGGaEKC830+QSiSUsLRlL/EyhXTmLcJc/5iDkMuOpUhNz0e0Q/nTqjVJ3ko00Q/oyE+jauHhUHfb1GxGHkE+++3+qCS4+ItkaA6tiItCo+romzElfLFD6RIj7oHt9vffs98nLwpHnaqKjufnLFMejSlAUGiQvTofIiGhIvftAMcoFV4mrUHsqyQ/ncQihmJHkbxXjvM57FCb6b9dEIRZl7jgj0+QLNLRs0NZ4azdZ6rzbGTSO8KA5I3Aq/3gBr87X16Mj0oJtaPKmFGaP2zghfOVhxQht8YjRd50lJa+Ue4PAuPSdu2O69DKLH8VOhrsB+psaBIRxnRi5POUQ6w8s8qlb9vxvExjHNOAKWXV1by1Nz+6FPWdyTeAgcmonjCcV0dCtPj/KyeVDkeSrDkKZjnDzHEqeCdfmJ65kve+Vy3YS0vagzyHfVEnzN0ULUZtkGfJXFNm6+bIa55wmGBhUeXbHL0EdlQXMu1YXxmcwBgTaq7tlQcfv7AefanbfjGE8R1IFnNyg2/jXLbnLg5Z6l1oKqgnxZQg0DE9BJuw6s0XjGwTdSxybWxp+WFD/RsXt76uwvCBk7z+YmSFLtFj2UlTsoq+vl0DTmsVItDKf9SZ94NcuJ7mxJYI02S/2kQBfbbHG0d4hXevDrEC0cb86EvzN2ud+v6bAunNRGNFz/RH0KLusoBVeo+puCFKeeIJWEo0t1UicX5YxJwMAoV7+g0gK93y4W9sMQtso8/wY5wsBzis9dwfLvIwXpaAM1g0MZp/YIRq8T/Qc+U/8x99tam4er0IWizvrkjqhIzCWBKpJ4Y4gj3bOmiS3VCMEaoVfKCwUWENwYKuP3H5VI0n+O2vVVRrekUrwvkm6URRhVhN4eEFTCjB9nSQu++qKyDH8HPpkS3YfwF8/OQtrZo7hQXxvNmP2HcH/K7zcweD00BaoOLiYUtXRItGYbl06sVSbm04soRf1Jqpyo3XiRqBWD9rmJfr4w8NOEGVGUCKXLDLsXy+8JC4Iqf0FsIjWxjMVdraTUtCbwXRbYUownQVm6bt7LYD1SNPoWNPqUJgsLMwP33ugrb1UbHCs24roOch6Go5QHIPA8E15SZE9pkr1SkmqrNs/+KRomFJ9HyFnWUYhZIV9MRLqlOAt6XBBTash3WJnCjhx/PZGhXVvdn2jX4+0Pm55LsiNugA8vaAUJQBxD/8a1u/RvTgbj35+b7I7m8tG0hMhClNZF+tpsOmZZhUGuXH9uVbkJMlMuAmMVCHwn3O31GlLeXXzzep2WS3xN2U+p5J0I7GySnuZUkuGs1ZTVqGUvR2g4q+7ljU55Ak78yPZiQXeUeqS74azszvZvCqWxXn2eePj+gcpliOjrYKpglUP19rQrMt8PqLt8L0ghIqVCmMwl3Hgr/VUcqDpXdpPTR=',
        'Timezone': 'Mon Feb 23 2026 22:06:02 GMT+0800',
        'Version': '0.2.7',
        'Origin': 'https://chat.qwen.ai',
    }
    
    MODEL_ALIASES = {
        'qwen': 'qwen3-max',
        'qwen3': 'qwen3-max',
        'qwen3.5': 'qwen3.5-plus',
        'qwen3-coder': 'qwen3-coder-plus',
        'qwen3-vl': 'qwen3-vl-235b-a22b',
        'qwen3-omni': 'qwen3-omni-flash',
        'qwen2.5': 'qwen2.5-max',
        'qwen3.5-max-preview': 'qwen3.5-max-2026-03-08',
    }
    
    def __init__(self, token: str, cookies: Optional[str] = None, use_proxy: bool = True):
        """Initialize Qwen AI Adapter
        
        Args:
            token: JWT token from chat.qwen.ai Local Storage
            cookies: Optional cookies string for enhanced compatibility
            use_proxy: Whether to use proxy (Vless or HTTP proxy)
        """
        self.token = token
        self.cookies = cookies
        self._force_thinking = None
        self.use_proxy = use_proxy
        
        # 初始化代理管理器
        if use_proxy:
            self.proxy_manager = init_proxy_manager()
            self.session = self.proxy_manager.create_session(use_vless=True)
        else:
            self.session = requests.Session()
        
        self.session.timeout = 120
    
    def _uuid(self) -> str:
        """Generate UUID"""
        return str(uuid.uuid4())
    
    def get_headers(self, chat_id: Optional[str] = None) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            **self.DEFAULT_HEADERS,
            'Authorization': f'Bearer {self.token}',
            'X-Request-Id': self._uuid(),
        }
        
        if chat_id:
            headers['Referer'] = f'https://chat.qwen.ai/c/{chat_id}'
        
        if self.cookies:
            headers['Cookie'] = self.cookies
        
        return headers
    
    def map_model(self, openai_model: str) -> str:
        """Map OpenAI model name to Qwen AI model name
        
        Supports thinking mode suffixes:
        - -think: Thinking mode (thinking_mode="Thinking")
        - -fast: Fast mode (thinking_mode="Fast")
        - no suffix: Auto mode (thinking_mode="Auto")
        """
        model = openai_model
        thinking_mode = "Auto"  # 默认自动模式
        
        if model.endswith('-think'):
            thinking_mode = "Thinking"
            model = model[:-6]
        elif model.endswith('-thinking'):
            thinking_mode = "Thinking"
            model = model[:-9]
        elif model.endswith('-fast'):
            thinking_mode = "Fast"
            model = model[:-5]
        
        self._thinking_mode = thinking_mode
        
        lower_model = model.lower()
        
        if lower_model in self.MODEL_ALIASES:
            return self.MODEL_ALIASES[lower_model]
        
        # Always return lowercase model name
        return model.lower()
    
    def create_chat(self, model_id: str, title: str = 'New Chat') -> str:
        """Create a new chat"""
        url = f'{self.QWEN_AI_BASE}/api/v2/chats/new'
        payload = {
            'title': title,
            'models': [model_id],
            'chat_mode': 'normal',
            'chat_type': 't2t',
            'timestamp': int(time.time() * 1000),
            'project_id': '',
        }
        
        response = self.session.post(
            url,
            json=payload,
            headers=self.get_headers(),
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        if not data.get('data', {}).get('id'):
            raise ValueError('Failed to create chat: no chat ID returned')
        
        return data['data']['id']
    
    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat"""
        url = f'{self.QWEN_AI_BASE}/api/v2/chats/{chat_id}'
        
        response = self.session.delete(
            url,
            headers=self.get_headers(),
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        return data.get('success', False)
    
    def delete_all_chats(self) -> bool:
        """Delete all chats"""
        url = f'{self.QWEN_AI_BASE}/api/v2/chats/'
        
        response = self.session.delete(
            url,
            headers=self.get_headers(),
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        return data.get('success', False)
    
    def chat_completion(self, model: str, messages: list, stream: bool = True,
                      temperature: Optional[float] = None, enable_thinking: Optional[bool] = None,
                      thinking_budget: Optional[int] = None,
                      auto_delete_chat: bool = False,
                      reasoning_mode: Optional[str] = None) -> Tuple[requests.Response, str, Optional[str]]:
        """Send chat completion request

        Args:
            auto_delete_chat: Whether to delete the chat after completion
            reasoning_mode: Thinking mode - "Auto", "Fast", or "Thinking"
        """
        if not self.token:
            raise ValueError('Qwen AI token not configured')

        model_id = self.map_model(model)

        # Determine thinking mode (priority: reasoning_mode param > model suffix > default)
        thinking_mode = reasoning_mode or getattr(self, '_thinking_mode', 'Auto')

        # Map thinking mode to feature_config values
        if thinking_mode == 'Fast':
            auto_thinking = False
            thinking_enabled = False
        elif thinking_mode == 'Thinking':
            auto_thinking = False
            thinking_enabled = True
        else:  # Auto
            auto_thinking = True
            thinking_enabled = True
        
        # Create new chat
        chat_id = self.create_chat(model_id, 'OpenAI_API_Chat')
        
        # Build conversation content from all messages
        system_content = ''
        conversation_parts = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_content += (system_content + '\n\n' if system_content else '') + msg['content']
            elif msg['role'] == 'user':
                conversation_parts.append(f"User: {msg['content']}")
            elif msg['role'] == 'assistant':
                conversation_parts.append(f"Assistant: {msg['content']}")
        
        # Combine all messages into user_content
        user_content = '\n\n'.join(conversation_parts)
        
        # Prepend system content
        if system_content:
            user_content = f'{system_content}\n\n{user_content}'
        
        fid = self._uuid()
        child_id = self._uuid()
        ts = int(time.time())
        
        feature_config = {
            'thinking_enabled': thinking_enabled,
            'output_schema': 'phase',
            'research_mode': 'normal',
            'auto_thinking': auto_thinking,
            'thinking_mode': thinking_mode,
            'thinking_format': 'summary',
            'auto_search': False,
        }

        if thinking_budget:
            feature_config['thinking_budget'] = thinking_budget
        
        payload = {
            'stream': True,  # Always stream to backend
            'version': '2.1',
            'incremental_output': True,
            'chat_id': chat_id,
            'chat_mode': 'normal',
            'model': model_id,
            'parent_id': None,
            'messages': [
                {
                    'fid': fid,
                    'parentId': None,
                    'childrenIds': [child_id],
                    'role': 'user',
                    'content': user_content,
                    'user_action': 'chat',
                    'files': [],
                    'timestamp': ts,
                    'models': [model_id],
                    'chat_type': 't2t',
                    'feature_config': feature_config,
                    'extra': {'meta': {'subChatType': 't2t'}},
                    'sub_chat_type': 't2t',
                    'parent_id': None,
                },
            ],
            'timestamp': ts + 1,
        }
        
        url = f'{self.QWEN_AI_BASE}/api/v2/chat/completions?chat_id={chat_id}'
        
        response = self.session.post(
            url,
            json=payload,
            headers={
                **self.get_headers(chat_id),
                'x-accel-buffering': 'no',
            },
            stream=True,
            timeout=120
        )
        
        response.raise_for_status()
        
        return response, chat_id, None
    
    @staticmethod
    def is_qwen_ai_provider(api_endpoint: str) -> bool:
        """Check if the API endpoint is Qwen AI"""
        return 'chat.qwen.ai' in api_endpoint
