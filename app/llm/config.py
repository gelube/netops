#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 配置模块"""
import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field


from enum import Enum


class ProviderType(str, Enum):
    """Provider 类型"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ALIYUN = "aliyun"
    CUSTOM = "custom"


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str = "openai"
    endpoint: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = ""
    available_models: List[str] = Field(default_factory=list)
    
    def save(self, config_dir: str = None) -> None:
        """保存配置到文件"""
        if config_dir is None:
            # 默认保存到项目 config 目录
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
        
        config_path = os.path.join(config_dir, "llm_config.json")
        
        # 确保目录存在
        os.makedirs(config_dir, exist_ok=True)
        
        config_data = {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "model": self.model,
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"LLM config saved to: {config_path}")
        except Exception as e:
            print(f"Failed to save config: {e}")
            raise
    
    @classmethod
    def load(cls, config_dir: str = None) -> "LLMConfig":
        """从文件加载配置"""
        if config_dir is None:
            # 默认从项目 config 目录加载
            config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
        
        config_path = os.path.join(config_dir, "llm_config.json")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return cls(
                        provider=data.get("provider", "openai"),
                        endpoint=data.get("endpoint", "https://api.openai.com/v1"),
                        model=data.get("model", ""),
                    )
            except Exception as e:
                print(f"Failed to load config: {e}")
        
        return cls()


class LLMClient:
    """LLM 客户端"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
    
    def _get_client(self):
        """获取 API 客户端"""
        if self._client is not None:
            return self._client
        
        if self.config.provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("Please install anthropic: pip install anthropic")
        else:
            # OpenAI 格式（兼容 OpenAI、阿里云、Ollama 等）
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.endpoint
                )
            except ImportError:
                raise ImportError("Please install openai: pip install openai")
        
        return self._client
    
    def chat_simple(self, user_message: str, context: str = "", timeout: int = 10) -> str:
        """简单对话（带超时）"""
        client = self._get_client()
        
        system_prompt = "你是一个网络运维助手。"
        if context:
            system_prompt += "\n" + context
        
        try:
            if self.config.provider == "anthropic":
                response = client.messages.create(
                    model=self.config.model or "claude-3-sonnet-20240229",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    timeout=timeout
                )
                return response.content[0].text
            else:
                # OpenAI 客户端支持 timeout 参数（秒）
                import httpx
                http_client = httpx.Client(timeout=timeout)
                response = client.chat.completions.create(
                    model=self.config.model or "gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    timeout=timeout
                )
                return response.choices[0].message.content
        except Exception as e:
            # 超时或连接失败时返回 None，让调用方降级处理
            print(f"LLM 调用失败（可能超时）: {e}")
            return None
    
    def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            client = self._get_client()
            if hasattr(client, 'models'):
                models = client.models.list()
                return [m.id for m in models.data] if hasattr(models, 'data') else []
            return []
        except Exception as e:
            print(f"Failed to list models: {e}")
            return []


class LLMConfigManager:
    """LLM 配置管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.config = LLMConfig.load()
            cls._instance.client = None
        return cls._instance
    
    def get_config(self) -> LLMConfig:
        return self.config
    
    def set_config(self, config: LLMConfig):
        self.config = config
        self.client = None
    
    def get_client(self) -> Optional[LLMClient]:
        if self.client is None and self.config:
            self.client = LLMClient(self.config)
        return self.client
