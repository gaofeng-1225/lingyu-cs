"""
场景管理（业务网关）
====================
- 从 server/scenes/*.json 加载场景定义，支持 ${ENV_VAR} 环境变量引用；
- 每次 getScenes 创建一个会话（Session），为每个场景动态生成
  RoomId / UserId / TaskId 并签发 RTC Token，避免固定房间互相冲突；
- 同一会话同一时刻只允许一个场景处于通话中（与官方约束一致）。
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from .token import build_rtc_token

router = APIRouter(tags=["gateway"])

SCENES_DIR = Path(__file__).resolve().parent.parent.parent / "scenes"

# 支持 ${VAR} 与 ${VAR:-默认值} 两种写法
_ENV_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}$")


def expand_env(value: Any) -> Any:
    """递归展开字符串中的 ${ENV_VAR} / ${ENV_VAR:-default} 引用。"""
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    if isinstance(value, str):
        match = _ENV_PATTERN.match(value)
        if match:
            return __import__("os").environ.get(match.group(1), match.group(2) or "")
        return value
    return value


def load_scene_definitions() -> Dict[str, Dict[str, Any]]:
    """读取 scenes/*.json，文件名（去后缀）即场景 ID。"""
    definitions: Dict[str, Dict[str, Any]] = {}
    if not SCENES_DIR.exists():
        return definitions
    for path in sorted(SCENES_DIR.glob("*.json")):
        try:
            definitions[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"场景文件 {path.name} 解析失败: {exc}") from exc
    return definitions


def _validate_definition(scene_id: str, definition: Dict[str, Any]) -> None:
    if not isinstance(definition, dict):
        raise ValueError(f"{scene_id}: 场景必须为 JSON 对象")
    if "SceneConfig" not in definition or not isinstance(definition["SceneConfig"], dict):
        raise ValueError(f"{scene_id}: 缺少 SceneConfig")
    voice_chat = definition.get("VoiceChat")
    if not isinstance(voice_chat, dict) or "Config" not in voice_chat or "AgentConfig" not in voice_chat:
        raise ValueError(f"{scene_id}: VoiceChat 必须包含 Config 与 AgentConfig")
    agent = voice_chat["AgentConfig"]
    if not isinstance(agent.get("UserId"), str) or not agent["UserId"].strip():
        raise ValueError(f"{scene_id}: AgentConfig.UserId 不能为空")


class RuntimeScene:
    """一个场景的运行时状态。"""

    def __init__(self, scene_id: str, definition: Dict[str, Any]) -> None:
        self.scene_id = scene_id
        self.definition = copy.deepcopy(definition)
        self.room_id = uuid.uuid4().hex[:16]
        self.user_id = uuid.uuid4().hex[:16]
        self.task_id = uuid.uuid4().hex[:16]
        self.status: str = "idle"  # idle | starting | active | stopping
        self.pending: Optional[asyncio.Task] = None

        scene_cfg = self.definition["SceneConfig"]
        voice_chat = self.definition["VoiceChat"]
        agent = voice_chat["AgentConfig"]

        self.scene = {
            "id": scene_id,
            "name": scene_cfg.get("name", scene_id),
            "icon": scene_cfg.get("icon", ""),
            "questions": scene_cfg.get("questions", []),
            "botName": agent["UserId"],
            "isInterruptMode": bool((voice_chat.get("Config") or {}).get("InterruptMode") == 0),
            "isAvatarScene": None,
            "avatarBgUrl": None,
            "isVision": False,
            "isScreenMode": False,
        }
        self.rtc = {
            "AppId": settings.RTC_APP_ID,
            "BusinessId": settings.RTC_BUSINESS_ID or None,
            "RoomId": self.room_id,
            "UserId": self.user_id,
            "Token": build_rtc_token(settings.RTC_APP_ID, settings.RTC_APP_KEY, self.room_id, self.user_id),
        }


class Session:
    """一次 getScenes 对应的会话：包含全部场景的运行时状态。"""

    def __init__(self, definitions: Dict[str, Dict[str, Any]]) -> None:
        self.id = uuid.uuid4().hex
        self.lock = asyncio.Lock()
        self.active_scene_id: Optional[str] = None
        self.scenes: Dict[str, RuntimeScene] = {
            sid: RuntimeScene(sid, definition) for sid, definition in definitions.items()
        }

    def to_payload(self) -> Dict[str, Any]:
        return {
            "SessionID": self.id,
            "scenes": [
                {"scene": scene.scene, "rtc": scene.rtc}
                for scene in self.scenes.values()
            ],
        }


# 全局会话注册表（内存态；生产可替换为 Redis / veDb）
_SESSIONS: Dict[str, Session] = {}
_DEFINITIONS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def get_definitions() -> Dict[str, Dict[str, Any]]:
    global _DEFINITIONS_CACHE
    if _DEFINITIONS_CACHE is None:
        _DEFINITIONS_CACHE = load_scene_definitions()
    return _DEFINITIONS_CACHE


def get_session(session_id: str) -> Session:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise KeyError(f"会话 {session_id} 不存在，请先调用 getScenes")
    return session


def create_session() -> Session:
    session = Session(get_definitions())
    _SESSIONS[session.id] = session
    return session


class ScenesRequest(BaseModel):
    pass


@router.post("/getScenes")
async def get_scenes() -> Dict[str, Any]:
    """获取可用场景列表与 RTC 入会信息（前端呼叫前调用）。"""
    try:
        definitions = get_definitions()
        if not definitions:
            raise HTTPException(status_code=500, detail=f"未找到任何场景配置，请检查 {SCENES_DIR} 目录")
        for sid, definition in definitions.items():
            _validate_definition(sid, definition)
        session = create_session()
        return {
            "ResponseMetadata": {"Action": "getScenes"},
            "Result": session.to_payload(),
        }
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
