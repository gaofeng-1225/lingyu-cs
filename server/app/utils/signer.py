"""
火山引擎 OpenAPI V4 签名（纯 Python 实现）
==========================================
不依赖官方 SDK，按火山引擎签名机制（HMAC-SHA256）手写实现，
用于 RTC OpenAPI 与知识库（air 服务）请求签名。

签名流程：
1. 构造 CanonicalRequest
2. 构造 StringToSign
3. 由 SK 派生 SigningKey
4. 计算 Signature 并拼装 Authorization 头
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

# 参与签名的 Header（火山引擎规范固定四项，必须小写排序）
_SIGNED_HEADERS = ("content-type", "host", "x-content-sha256", "x-date")


def _hmac_sha256(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _urlencode_query(params: Mapping[str, Any]) -> str:
    """Query 参数按 key 排序、value 做百分号编码，拼接成规范串。"""
    from urllib.parse import quote

    pairs = []
    for key in sorted(params):
        pairs.append(f"{quote(str(key), safe='')}={quote(str(params[key]), safe='')}")
    return "&".join(pairs)


def sign_request(
    *,
    access_key_id: str,
    secret_key: str,
    service: str,
    region: str,
    method: str,
    path: str,
    params: Mapping[str, Any],
    headers: Mapping[str, str],
    body: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, str]:
    """
    对请求进行 V4 签名，返回可直接发送的 headers（含 Authorization）。
    body 会被序列化两次（签名哈希 + 实际发送），因此调用方必须使用
    ``body_bytes`` 中返回的字节作为请求体，保证哈希一致。
    """
    body_bytes = (
        json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if body
        else b""
    )
    now = now or datetime.now(timezone.utc)
    short_date = now.strftime("%Y%m%d")
    x_date = now.strftime("%Y%m%dT%H%M%SZ")

    # 规范化 Header：只保留四项签名头，值 trim、去空白
    header_map = {k.lower(): v.strip() for k, v in headers.items()}
    canonical_headers = "".join(
        f"{name}:{header_map.get(name, '')}\n" for name in _SIGNED_HEADERS
    )
    signed_headers = ";".join(_SIGNED_HEADERS)

    canonical_request = "\n".join(
        [
            method.upper(),
            path,
            _urlencode_query(params),
            canonical_headers,
            signed_headers,
            _sha256_hex(body_bytes),
        ]
    )

    credential_scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            credential_scope,
            _sha256_hex(canonical_request.encode("utf-8")),
        ]
    )

    k_date = _hmac_sha256(secret_key.encode("utf-8"), short_date.encode("utf-8"))
    k_region = _hmac_sha256(k_date, region.encode("utf-8"))
    k_service = _hmac_sha256(k_region, service.encode("utf-8"))
    k_signing = _hmac_sha256(k_service, b"request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    signed_headers_map = {
        "X-Date": x_date,
        "X-Content-Sha256": _sha256_hex(body_bytes),
        "Authorization": authorization,
    }
    return {"headers": signed_headers_map, "body": body_bytes}
