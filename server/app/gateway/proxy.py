"""
RTC OpenAPI 代理（业务网关）
============================
前端不直接持有 AK/SK，所有 StartVoiceChat / StopVoiceChat 动作经由此接口
签名后转发到火山引擎 RTC OpenAPI。

关键点：
- Action 白名单校验；
- StartVoiceChat 使用场景中配置的 ASR、LLM、TTS 参数；
- 房间/任务维度防重复启动。
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from ..config import settings
from ..utils.signer import sign_request
from .scenes import Session, expand_env, get_session

logger = logging.getLogger("lingyu.gateway")

router = APIRouter(tags=["gateway"])

START_ACTION = "StartVoiceChat"
STOP_ACTION = "StopVoiceChat"
ALLOWED_ACTIONS = {START_ACTION, STOP_ACTION}


class ProxyBody(BaseModel):
    SessionID: str
    SceneID: str


def _build_start_request(session: Session, scene_id: str) -> Dict[str, Any]:
    scene = session.scenes[scene_id]
    # 场景 JSON 中的 ${ENV_VAR} 引用在发送前展开
    voice_chat = expand_env(copy.deepcopy(scene.definition["VoiceChat"]))
    agent_config = copy.deepcopy(voice_chat.get("AgentConfig", {}))
    agent_config.update(
        {
            "TargetUserId": [scene.user_id],
            "EnableConversationStateCallback": True,
        }
    )
    config = copy.deepcopy(voice_chat.get("Config", {}))

    request_body: Dict[str, Any] = {
        "AppId": settings.RTC_APP_ID,
        "RoomId": scene.room_id,
        "TaskId": scene.task_id,
        "AgentConfig": agent_config,
        "Config": config,
    }
    if settings.RTC_BUSINESS_ID:
        request_body["BusinessId"] = settings.RTC_BUSINESS_ID
    return request_body


def _build_stop_request(session: Session, scene_id: str) -> Dict[str, Any]:
    scene = session.scenes[scene_id]
    return {
        "AppId": settings.RTC_APP_ID,
        "RoomId": scene.room_id,
        "TaskId": scene.task_id,
    }


async def _invoke_openapi(action: str, request_body: Dict[str, Any]) -> Dict[str, Any]:
    """签名并调用 RTC OpenAPI。"""
    endpoint = settings.RTC_ENDPOINT.rstrip("/")
    params = {"Action": action, "Version": settings.RTC_API_VERSION}

    base_headers = {
        "Host": endpoint.split("//")[-1],
        "Content-Type": "application/json",
    }
    signed = sign_request(
        access_key_id=settings.VOLC_ACCESS_KEY,
        secret_key=settings.VOLC_SECRET_KEY,
        service="rtc",
        region=settings.RTC_REGION,
        method="POST",
        path="/",
        params=params,
        headers=base_headers,
        body=request_body,
    )
    headers = {**base_headers, **signed["headers"]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            endpoint,
            params=params,
            headers=headers,
            content=signed["body"],
        )
    try:
        return response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail=f"火山引擎返回非 JSON: {response.text[:200]}")


def _response_succeeded(response: Dict[str, Any]) -> bool:
    return not (response.get("ResponseMetadata") or {}).get("Error")


@router.post("/proxy")
async def proxy(
    body: ProxyBody,
    action: str = Query(..., alias="Action", description="StartVoiceChat / StopVoiceChat"),
) -> Dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Action 仅支持 {sorted(ALLOWED_ACTIONS)}")

    try:
        session: Session = get_session(body.SessionID)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.SceneID not in session.scenes:
        raise HTTPException(status_code=404, detail=f"场景 {body.SceneID} 不存在")

    scene = session.scenes[body.SceneID]

    async with session.lock:
        if action == START_ACTION:
            if scene.status == "starting":
                raise HTTPException(status_code=409, detail="语音对话正在启动中，请稍候")
            if scene.status == "stopping":
                raise HTTPException(status_code=409, detail="语音对话正在停止，请稍后重试")
            if scene.status == "active":
                return {
                    "ResponseMetadata": {"Action": START_ACTION, "RequestId": "local-idempotent"},
                    "Result": "ok",
                }
            if session.active_scene_id and session.active_scene_id != body.SceneID:
                raise HTTPException(
                    status_code=409,
                    detail=f"同一会话仅允许一个场景通话，当前活动场景: {session.active_scene_id}",
                )
            session.active_scene_id = body.SceneID
            scene.status = "starting"
            try:
                request_body = _build_start_request(session, body.SceneID)
                logger.info("StartVoiceChat -> %s", request_body)
                result = await _invoke_openapi(START_ACTION, request_body)
                if _response_succeeded(result):
                    scene.status = "active"
                    from ..aicore.sessions import create_voice_session

                    create_voice_session(
                        session_id=session.id,
                        scene_id=body.SceneID,
                        room_id=scene.room_id,
                        user_id=scene.user_id,
                        bot_name=scene.scene["botName"],
                    )
                else:
                    session.active_scene_id = None
                    scene.status = "idle"
                return result
            except Exception as exc:
                session.active_scene_id = None
                scene.status = "idle"
                logger.exception("StartVoiceChat 失败")
                raise HTTPException(status_code=502, detail=f"启动语音对话失败: {exc}") from exc

        # StopVoiceChat
        if scene.status == "idle":
            return {
                "ResponseMetadata": {"Action": STOP_ACTION, "RequestId": "local-idempotent"},
                "Result": "ok",
            }
        if scene.status == "starting":
            raise HTTPException(status_code=409, detail="语音对话尚未启动完成，请稍后重试")
        if scene.status == "stopping":
            return {
                "ResponseMetadata": {"Action": STOP_ACTION, "RequestId": "local-idempotent"},
                "Result": "ok",
            }
        scene.status = "stopping"
        try:
            request_body = _build_stop_request(session, body.SceneID)
            result = await _invoke_openapi(STOP_ACTION, request_body)
            if _response_succeeded(result):
                scene.status = "idle"
            else:
                scene.status = "active"
            if session.active_scene_id == body.SceneID:
                session.active_scene_id = None
            from ..aicore.sessions import end_voice_session

            end_voice_session(session.id)
            return result
        except Exception as exc:
            scene.status = "active"
            logger.exception("StopVoiceChat 失败")
            raise HTTPException(status_code=502, detail=f"停止语音对话失败: {exc}") from exc
