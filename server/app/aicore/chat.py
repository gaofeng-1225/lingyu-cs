"""
调试与运营接口（AI 中枢 · 调试台）
==================================
配合 Swagger UI（/docs）使用，抽离核心业务逻辑（RAG 查询、LLM 问答、
回调模拟），方便不启动 RTC 即可联调与验收，也是团队开发效率工具。
"""

from __future__ import annotations

import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..config import settings
from .llm import LLMError, llm_service
from .prompt import build_messages
from .rag import rag_service
from .sessions import list_call_logs, list_voice_sessions, log_call

logger = logging.getLogger("lingyu.aicore.chat")

router = APIRouter(tags=["aicore-debug"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    """文本对话请求。"""
    question: str
    history: List[ChatMessage] = []
    stream: bool = True


class CallbackSimRequest(BaseModel):
    """模拟 RTC 云端回调请求体。"""
    messages: List[ChatMessage]
    scene: str = "debug"


@router.post("/api/v1/chat")
async def chat(request: ChatRequest):
    """通用流式对话（调试 / 二次开发用）：返回纯文本 SSE 流。"""
    history = [{"role": m.role, "content": m.content} for m in request.history]
    history.append({"role": "user", "content": request.question})

    if not request.stream:
        rag_context = await rag_service.retrieve(request.question)
        messages = build_messages(history, rag_context)
        try:
            return JSONResponse({"answer": await llm_service.complete(messages)})
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    async def generate():
        rag_context = await rag_service.retrieve(request.question)
        messages = build_messages(history, rag_context)
        try:
            async for chunk in llm_service.stream_chat(messages):
                choices = chunk.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                if delta.get("content"):
                    yield f"data: {json.dumps({'content': delta['content']}, ensure_ascii=False)}\n\n"
        except LLMError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/debug/chat")
async def debug_chat(request: ChatRequest):
    """同 /api/v1/chat，调试台别名。"""
    return await chat(request)


@router.get("/debug/rag")
async def debug_rag(query: str = Query(..., description="检索问题")):
    """直接查看知识库检索结果（不经过 LLM）。"""
    context = await rag_service.retrieve(query)
    return {
        "query": query,
        "mode": settings.KB_MODE,
        "retrieved_length": len(context),
        "retrieved_context": context,
        "status": "success" if context else "empty",
    }


@router.post("/debug/callback")
async def debug_callback(request: CallbackSimRequest):
    """模拟 RTC 云端回调：用同样的 SSE 协议跑一遍完整链路。"""
    from .callback import chat_callback  # 复用回调实现

    return await chat_callback(request)


@router.get("/debug/scenes")
async def debug_scenes():
    """列出当前已加载的场景与 AI 配置摘要（脱敏）。"""
    from ..gateway.scenes import expand_env, get_definitions

    definitions = get_definitions()
    result = []
    for scene_id, definition in definitions.items():
        voice_chat = expand_env(definition.get("VoiceChat", {}))
        config = voice_chat.get("Config", {})
        result.append(
            {
                "scene_id": scene_id,
                "name": definition.get("SceneConfig", {}).get("name"),
                "bot_name": voice_chat.get("AgentConfig", {}).get("UserId"),
                "welcome": voice_chat.get("AgentConfig", {}).get("WelcomeMessage"),
                "llm_mode": (config.get("LLMConfig") or {}).get("Mode", "CustomLLM"),
                "callback_url": settings.callback_url,
                "asr_mode": (config.get("ASRConfig") or {}).get("ProviderParams", {}).get("Mode"),
                "tts_voice": (config.get("TTSConfig") or {}).get("ProviderParams", {})
                .get("audio", {}).get("voice_type"),
            }
        )
    return {"scenes": result, "kb_mode": settings.KB_MODE}


@router.get("/api/call-logs")
async def call_logs(limit: int = Query(50, ge=1, le=500)):
    """查看最近的通话日志（含 RAG/LLM 耗时、Token、敏感词命中）。"""
    return {"logs": list_call_logs(limit)}


@router.get("/api/voice-sessions")
async def voice_sessions(limit: int = Query(50, ge=1, le=500)):
    """查看语音会话记录。"""
    return {"sessions": list_voice_sessions(limit)}


@router.get("/api/health")
async def health():
    return {"ok": True, "app": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/api/env-check")
async def env_check():
    """环境自检：逐项列出关键配置是否就绪（只显示脱敏状态）。"""
    missing = settings.missing_required()
    return {
        "app": settings.APP_NAME,
        "kb_mode": settings.KB_MODE,
        "callback_url": settings.callback_url or "（未配置 SERVER_URL，RTC 联调前必须配置）",
        "items": [{"name": name, "ready": ready} for name, ready in missing.items()],
        "all_ready": all(missing.values()),
    }
