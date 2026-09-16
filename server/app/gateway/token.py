"""
RTC 房间 AccessToken 签发
==========================
二进制协议与火山官方 token.js 一致：
  token = "001" + appId(24) + base64( content )
  content = u16len(msg) + msg + u16len(sig) + sig
  msg = nonce(u32) + issuedAt(u32) + expireAt(u32)
        + roomId(str) + userId(str) + privileges(treeMap)
  sig = HMAC-SHA256(appKey, msg)
"""

from __future__ import annotations

import hashlib
import hmac
import random
import struct
import time
from typing import Dict

VERSION = "001"
APP_ID_LENGTH = 24

# 权限位（与官方一致）
PRIV_PUBLISH_STREAM = 0
PRIV_PUBLISH_AUDIO_STREAM = 1
PRIV_PUBLISH_VIDEO_STREAM = 2
PRIV_PUBLISH_DATA_STREAM = 3
PRIV_SUBSCRIBE_STREAM = 4


def _hmac_sha256(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def _pack_msg(nonce: int, issued_at: int, expire_at: int, room_id: str, user_id: str,
              privileges: Dict[int, int]) -> bytes:
    buf = bytearray()

    def put_u32(v: int) -> None:
        buf.extend(struct.pack("<I", v))

    def put_u16(v: int) -> None:
        buf.extend(struct.pack("<H", v))

    def put_bytes(b: bytes) -> None:
        put_u16(len(b))
        buf.extend(b)

    def put_str(s: str) -> None:
        put_bytes(s.encode("utf-8"))

    put_u32(nonce)
    put_u32(issued_at)
    put_u32(expire_at)
    put_str(room_id)
    put_str(user_id)
    put_u16(len(privileges))
    for key in sorted(privileges):
        put_u16(key)
        put_u32(privileges[key])
    return bytes(buf)


def build_rtc_token(app_id: str, app_key: str, room_id: str, user_id: str,
                    expire_seconds: int = 24 * 3600) -> str:
    """签发一个可加入指定房间的 RTC Token。"""
    import base64

    if len(app_id) != APP_ID_LENGTH:
        raise ValueError(f"AppId 长度必须为 {APP_ID_LENGTH} 位，当前: {app_id}")

    nonce = random.getrandbits(32)
    now = int(time.time())
    expire_at = now + expire_seconds

    privileges = {
        PRIV_PUBLISH_STREAM: 0,
        PRIV_PUBLISH_AUDIO_STREAM: 0,
        PRIV_PUBLISH_VIDEO_STREAM: 0,
        PRIV_PUBLISH_DATA_STREAM: 0,
        PRIV_SUBSCRIBE_STREAM: 0,
    }

    msg = _pack_msg(nonce, now, expire_at, room_id, user_id, privileges)
    signature = _hmac_sha256(app_key.encode("utf-8"), msg)

    # content = u16len(msg) + msg + u16len(sig) + sig
    content = bytearray()
    content.extend(struct.pack("<H", len(msg)))
    content.extend(msg)
    content.extend(struct.pack("<H", len(signature)))
    content.extend(signature)

    return VERSION + app_id + base64.b64encode(bytes(content)).decode("ascii")
