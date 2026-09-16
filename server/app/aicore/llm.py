"""
大模型服务（AI 中枢）
=====================
基于 OpenAI 兼容协议（httpx 直连，不依赖 SDK）调用方舟 ARK 豆包模型，
支持流式（SSE）与非流式两种模式。

- 流式：直接透传 ARK 返回的 OpenAI 格式 chunk，供 RTC 回调 / 调试台使用；
- 非流式：用于批量评测等离线场景。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from ..config import settings

logger = logging.getLogger("lingyu.aicore.llm")


class LLMError(RuntimeError):
    pass


class LLMService:
    def __init__(self) -> None:
        self.base_url = settings.ARK_BASE_URL.rstrip("/")
        self.api_key = settings.ARK_API_KEY
        self.model = settings.effective_model

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: List[Dict[str, str]], stream: bool) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "stream": stream,
            "stream_options": {"include_usage": True} if stream else None,
        }

    # ---------- 流式 ----------
    async def stream_chat(self, messages: List[Dict[str, str]]) -> AsyncIterator[Dict[str, Any]]:
        """流式对话，逐条产出 ARK 返回的 OpenAI 格式 chunk（dict）。"""
        if not self.api_key or not self.model:
            raise LLMError("缺少 ARK_API_KEY 或 ARK_ENDPOINT_ID/LLM_MODEL，请在 server/.env 中配置")

        url = f"{self.base_url}/chat/completions"
        payload = self._payload(messages, stream=True)

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                async with client.stream(
                    "POST", url, headers=self._headers, json=payload
                ) as response:
                    if response.status_code != 200:
                        text = (await response.aread()).decode("utf-8", errors="ignore")
                        raise LLMError(f"ARK 返回 {response.status_code}: {text[:300]}")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning("忽略无法解析的 SSE 行: %s", data[:100])
        except httpx.HTTPError as exc:
            raise LLMError(f"调用 ARK 失败: {exc}") from exc

    # ---------- 非流式（评测用） ----------
    async def complete(self, messages: List[Dict[str, str]]) -> str:
        """非流式对话，返回完整文本。"""
        url = f"{self.base_url}/chat/completions"
        payload = self._payload(messages, stream=False)
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            response = await client.post(url, headers=self._headers, json=payload)
        if response.status_code != 200:
            raise LLMError(f"ARK 返回 {response.status_code}: {response.text[:300]}")
        data = response.json()
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")


llm_service = LLMService()
