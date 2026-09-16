"""
RTC 云端回调（AI 中枢 · 核心）
===============================
火山引擎 RTC 云端在 CustomLLM 模式下，把 ASR 识别出的用户文本以
OpenAI 兼容的 messages 结构 POST 到本接口（即 LLMConfig.Url）：

    POST /api/chat_callback
    { "messages": [{"role": "user", "content": "你们的课程多少钱？"}, ...] }

本服务依次完成：RAG 检索 → 提示词编排 → 豆包流式生成，
并以 SSE 流（OpenAI 格式 chunk）返回，云端再交给 TTS 播报。

同时落库通话日志（耗时/Token/敏感词命中），支撑运营复盘。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import settings
from .llm import LLMError, llm_service
from .prompt import build_messages
from .rag import rag_service
from .sessions import log_call

logger = logging.getLogger("lingyu.aicore.callback")

router = APIRouter(tags=["aicore"])

_FALLBACK_REPLY = "抱歉，AI 服务暂时开小差了，请稍后再试一次。"


def _check_sensitive(text: str) -> str:
    """命中敏感词返回命中词，否则返回空串。"""
    lowered = text.lower()
    for word in settings.SENSITIVE_WORDS:
        if word.lower() in lowered:
            return word
    return ""


def _sse_payload(data: Any) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/api/chat_callback")
async def chat_callback(request: Request):
    """RTC 云端第三方大模型回调：流式返回 OpenAI 兼容 SSE。"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    messages: List[Dict[str, str]] = body.get("messages") or []
    if not messages or messages[-1].get("role") != "user":
        # 非用户主动发言（如系统消息），按协议返回空文本
        return JSONResponse({"text": ""})

    user_text: str = messages[-1].get("content", "").strip()
    scene: str = body.get("scene") or "voice"
    hit_word = _check_sensitive(user_text)

    async def generate():
        rag_ms = llm_ms = first_token_ms = None
        tokens = None
        reply_parts: List[str] = []
        start = time.perf_counter()
        rag_start = time.perf_counter()

        rag_context = ""
        if hit_word:
            # 命中敏感词：直接兜底话术，不再进 LLM
            reply_parts.append(settings.SENSITIVE_REPLY)
            yield _sse_payload(
                {
                    "choices": [{"index": 0, "delta": {"content": settings.SENSITIVE_REPLY},
                                 "finish_reason": None}]
                }
            )
            yield _sse_payload(
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            )
            yield "data: [DONE]\n\n"
            log_call(scene=scene, user_text=user_text, reply="".join(reply_parts),
                     model=settings.effective_model, rag_ms=0.0, llm_ms=0.0,
                     first_token_ms=0.0, tokens=0, hit_sensitive=True)
            return

        rag_context = await rag_service.retrieve(user_text)
        rag_ms = (time.perf_counter() - rag_start) * 1000

        # 最近 N 轮历史（保留最后 2N 条消息，兼顾上下文与成本）
        history = messages[-settings.LLM_HISTORY_LENGTH * 2 :]
        final_messages = build_messages(history, rag_context)
        llm_start = time.perf_counter()

        try:
            async for chunk in llm_service.stream_chat(final_messages):
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - llm_start) * 1000
                choices = chunk.get("choices") or []
                if choices and choices[0].get("delta", {}).get("content"):
                    reply_parts.append(choices[0]["delta"]["content"])
                usage = chunk.get("usage")
                if usage:
                    tokens = usage.get("total_tokens")
                yield _sse_payload(chunk)  # 透传 OpenAI 格式 chunk
        except LLMError as exc:
            logger.error("LLM 调用失败: %s", exc)
            reply_parts.append(_FALLBACK_REPLY)
            yield _sse_payload(
                {"choices": [{"index": 0, "delta": {"content": _FALLBACK_REPLY},
                              "finish_reason": None}]}
            )
            yield _sse_payload(
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            )
        finally:
            llm_ms = (time.perf_counter() - llm_start) * 1000
            yield "data: [DONE]\n\n"
            total = (time.perf_counter() - start) * 1000
            logger.info(
                "回调完成: rag=%.0fms llm=%.0fms total=%.0fms tokens=%s reply_len=%d",
                rag_ms or 0, llm_ms or 0, total, tokens, len("".join(reply_parts)),
            )
            log_call(scene=scene, user_text=user_text, reply="".join(reply_parts),
                     model=settings.effective_model, rag_ms=rag_ms, llm_ms=llm_ms,
                     first_token_ms=first_token_ms, tokens=tokens)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
