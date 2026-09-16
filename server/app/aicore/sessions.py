"""
会话与通话日志管理（AI 中枢）
==============================
SQLite 轻量持久化，两张表：
- voice_sessions：一次语音通话会话（网关启停时写入）
- call_logs：一次 LLM 对话记录（回调/调试接口写入，含耗时与 Token）

生产环境可平滑替换为 veDb / MySQL / Redis（接口不变）。
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings

logger = logging.getLogger("lingyu.aicore.sessions")

_local = threading.local()
_DB_LOCK = threading.Lock()


def _db_path() -> Path:
    path = Path(settings.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(_db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
    return conn


def init_db() -> None:
    with _DB_LOCK:
        conn = _conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS voice_sessions (
                id TEXT PRIMARY KEY,
                scene_id TEXT,
                room_id TEXT,
                user_id TEXT,
                bot_name TEXT,
                created_at REAL,
                ended_at REAL
            );
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL,
                scene TEXT,
                role TEXT,
                user_text TEXT,
                reply TEXT,
                model TEXT,
                rag_ms REAL,
                llm_ms REAL,
                first_token_ms REAL,
                tokens INTEGER,
                hit_sensitive INTEGER DEFAULT 0
            );
            """
        )
        conn.commit()


# ---------- 语音会话 ----------

def create_voice_session(session_id: str, scene_id: str, room_id: str,
                         user_id: str, bot_name: str) -> None:
    try:
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO voice_sessions (id, scene_id, room_id, user_id, bot_name, created_at, ended_at)"
            " VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (session_id, scene_id, room_id, user_id, bot_name, time.time()),
        )
        conn.commit()
    except sqlite3.Error as exc:
        logger.warning("写入 voice_sessions 失败: %s", exc)


def end_voice_session(session_id: str) -> None:
    try:
        conn = _conn()
        conn.execute(
            "UPDATE voice_sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (time.time(), session_id),
        )
        conn.commit()
    except sqlite3.Error as exc:
        logger.warning("更新 voice_sessions 失败: %s", exc)


# ---------- 通话日志 ----------

def log_call(*, scene: str, user_text: str, reply: str, model: str,
             rag_ms: Optional[float], llm_ms: Optional[float],
             first_token_ms: Optional[float], tokens: Optional[int],
             hit_sensitive: bool = False) -> None:
    try:
        conn = _conn()
        conn.execute(
            "INSERT INTO call_logs (created_at, scene, role, user_text, reply, model,"
            " rag_ms, llm_ms, first_token_ms, tokens, hit_sensitive)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), scene, "voice", user_text, reply, model,
             rag_ms, llm_ms, first_token_ms, tokens, 1 if hit_sensitive else 0),
        )
        conn.commit()
    except sqlite3.Error as exc:
        logger.warning("写入 call_logs 失败: %s", exc)


def list_call_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM call_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]


def list_voice_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM voice_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]
