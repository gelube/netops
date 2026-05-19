#!/usr/bin/env python3
"""LLM 配置模块"""

import os
import json
import httpx
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

from app.logger import get_logger

log = get_logger(__name__)

# Fernet 加密（与 credentials.py 共享密钥）
try:
    from cryptography.fernet import Fernet

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


def _get_fernet() -> Optional["Fernet"]:
    """获取 Fernet 实例（密钥与 credentials.py 共享 ~/.netops/fernet.key）"""
    if not _HAS_CRYPTO:
        return None
    key_path = os.path.join(os.path.expanduser("~"), ".netops", "fernet.key")
    if not os.path.exists(key_path):
        return None
    try:
        with open(key_path, "rb") as f:
            key = f.read().strip()
        return Fernet(key)
    except Exception:
        return None


def _encrypt_api_key(api_key: str) -> str:
    """加密 API Key，失败时返回原文并打印警告"""
    if not api_key:
        return ""
    f = _get_fernet()
    if f is None:
        log.info("[WARN] Fernet 不可用，API Key 将明文存储")
        return api_key
    try:
        return f.encrypt(api_key.encode()).decode()
    except Exception:
        log.error("[WARN] API Key 加密失败，将明文存储")
        return api_key


def _decrypt_api_key(encrypted: str) -> str:
    """解密 API Key，失败时返回原文（可能是明文或损坏的密文）"""
    if not encrypted:
        return ""
    f = _get_fernet()
    if f is None:
        return encrypted  # 无 Fernet，当明文处理
    try:
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        # 解密失败 = 明文存储的旧数据，直接返回
        return encrypted


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

    def save(self, config_dir: str = "~/.netops-ai") -> None:
        """保存配置到文件"""
        config_path = os.path.join(os.path.expanduser(config_dir), "llm_config.json")

        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        # 简单实现：只保存非敏感配置
        config_data = {
            "provider": self.provider.value,
            "endpoint": self.endpoint,
            "model": self.model,
        }

        import json

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            log.info(f"LLM config saved to: {config_path}")
        except Exception as e:
            log.error(f"Failed to save config: {e}")
            raise

    @classmethod
    def load(cls, config_dir: str = None) -> "LLMConfig":
        """从文件加载配置"""
        if config_dir is None:
            # 默认从项目 config 目录加载
            config_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config"
            )

        config_path = os.path.join(config_dir, "llm_config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(
                        provider=data.get("provider", "openai"),
                        endpoint=data.get("endpoint", "https://api.openai.com/v1"),
                        model=data.get("model", ""),
                        api_key=_decrypt_api_key(data.get("api_key", "")),
                    )
            except Exception as e:
                log.error(f"Failed to load config: {e}")

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

                kwargs = {}
                if self.config.api_key:
                    kwargs["api_key"] = self.config.api_key
                self._client = anthropic.Anthropic(**kwargs)
            except ImportError:
                raise ImportError("Please install anthropic: pip install anthropic")
        else:
            # OpenAI 格式（兼容 OpenAI、阿里云、Ollama 等）
            try:
                from openai import OpenAI

                # 免凭证（Ollama等本地部署）：api_key不能传空字符串，用占位符
                api_key = self.config.api_key or "sk-no-key-required"
                from httpx import Client as HttpxClient

                # 配置连接池：超时+连接复用+keep-alive，防止CLOSE_WAIT泄漏
                http_client = HttpxClient(
                    timeout=60.0,
                    limits=httpx.Limits(
                        max_connections=10, max_keepalive_connections=5
                    ),
                )
                self._client = OpenAI(
                    api_key=api_key,
                    base_url=self.config.endpoint,
                    http_client=http_client,
                    timeout=60.0,
                )
            except ImportError:
                raise ImportError("Please install openai: pip install openai")

        return self._client

    def chat_simple(
        self, user_message: str, context: str = "", timeout: int = 10
    ) -> str:
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
                    timeout=timeout,
                )
                return response.content[0].text
            else:
                # 复用 _get_client() 返回的 OpenAI 客户端（已内置连接池），不再每次新建 httpx.Client
                response = client.chat.completions.create(
                    model=self.config.model or "gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    timeout=timeout,
                )
                return response.choices[0].message.content
        except Exception as e:
            # 超时或连接失败时返回 None，让调用方降级处理
            log.error(f"LLM 调用失败（可能超时）: {e}")
            return None

    def chat(
        self,
        messages: list,
        tools: list = None,
        temperature: float = 0.7,
        timeout: int = 30,
        tool_choice: str = "auto",
    ) -> dict:
        """
        完整对话接口 — 支持 function calling / tool use

        Args:
            messages: OpenAI 格式消息列表
            tools: OpenAI 格式工具定义列表
            temperature: 温度参数
            timeout: 超时秒数

        Returns:
            {"content": str, "tool_calls": [...] 或 None}
        """
        client = self._get_client()

        try:
            if self.config.provider == "anthropic":
                # Anthropic 的 tool use 格式不同，做适配
                system_msg = ""
                anthropic_msgs = []
                for m in messages:
                    if m["role"] == "system":
                        system_msg = m["content"]
                    else:
                        anthropic_msgs.append(m)

                kwargs = {
                    "model": self.config.model or "claude-3-sonnet-20240229",
                    "max_tokens": 2048,
                    "messages": anthropic_msgs,
                    "temperature": temperature,
                    "timeout": timeout,
                }
                if system_msg:
                    kwargs["system"] = system_msg

                if tools:
                    # 将 OpenAI tools 格式转为 Anthropic tools 格式
                    claude_tools = []
                    for t in tools:
                        if t.get("type") == "function":
                            func = t["function"]
                            claude_tools.append(
                                {
                                    "name": func["name"],
                                    "description": func.get("description", ""),
                                    "input_schema": func.get(
                                        "parameters",
                                        {"type": "object", "properties": {}},
                                    ),
                                }
                            )
                    if claude_tools:
                        kwargs["tools"] = claude_tools

                response = client.messages.create(**kwargs)

                result = {"content": "", "tool_calls": None}
                tool_calls = []
                text_parts = []
                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)
                    elif block.type == "tool_use":
                        tool_calls.append(
                            {
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input),
                                },
                            }
                        )

                result["content"] = "\n".join(text_parts)
                result["tool_calls"] = tool_calls if tool_calls else None
                return result

            else:
                # OpenAI 兼容格式（含 Ollama、阿里云等）
                kwargs = {
                    "model": self.config.model or "gpt-3.5-turbo",
                    "messages": messages,
                    "temperature": temperature,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = tool_choice

                response = client.chat.completions.create(**kwargs)
                choice = response.choices[0]

                result = {
                    "content": choice.message.content or "",
                    "tool_calls": None,
                }

                if choice.message.tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in choice.message.tool_calls
                    ]

                return result

        except Exception as e:
            log.error("LLM chat 调用失败", error=str(e))
            return {"content": None, "tool_calls": None, "error": str(e)}

    def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            client = self._get_client()
            if hasattr(client, "models"):
                models = client.models.list()
                return [m.id for m in models.data] if hasattr(models, "data") else []
            return []
        except Exception as e:
            log.error(f"Failed to list models: {e}")
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
