"""
知识库检索（AI 中枢）
=====================
双引擎设计：
- vikingdb 模式：调用火山引擎知识库 OpenAPI（air 服务，V4 签名），
  对应控制台 https://console.volcengine.com/vikingdb/knowledge 创建的集合；
- local 模式：读取本地 JSON 知识库（无需火山账号，便于先联调跑通链路），
  基于关键词打分检索，作为 VikingDB 的降级/演示方案。

检索结果统一返回拼接后的上下文文本，供提示词编排使用。
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings
from ..utils.signer import sign_request

logger = logging.getLogger("lingyu.aicore.rag")

# 检索打分参数
_LOCAL_SCORE_WEIGHT_TITLE = 3.0
_LOCAL_SCORE_WEIGHT_TAGS = 2.0


def _tokenize(text: str) -> List[str]:
    """简单中文/英文分词：中文按二元组切，英文按词切。"""
    text = text.lower()
    tokens: List[str] = []
    # 英文与数字词
    tokens.extend(re.findall(r"[a-z0-9]+", text))
    # 中文连续片段 -> 二元组
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(seg) == 1:
            tokens.append(seg)
        else:
            tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))
            tokens.append(seg)  # 整段也作为特征，利于长名词命中
    return tokens


class RagService:
    def __init__(self) -> None:
        self.mode = settings.KB_MODE

    # ---------- 对外统一入口 ----------
    async def retrieve(self, query: str, limit: Optional[int] = None) -> str:
        limit = limit or settings.KB_LIMIT
        start = time.perf_counter()
        if self.mode == "vikingdb":
            context = await self._retrieve_vikingdb(query, limit)
        else:
            context = self._retrieve_local(query, limit)
        cost = (time.perf_counter() - start) * 1000
        logger.info("RAG 检索耗时 %.0fms, 命中长度 %d", cost, len(context))
        return context

    # ---------- 本地 JSON 知识库 ----------
    def _load_local_kb(self) -> List[Dict[str, Any]]:
        path = Path(settings.KB_LOCAL_FILE)
        if not path.exists():
            logger.warning("本地知识库文件不存在: %s", path)
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else data.get("documents", [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("本地知识库读取失败: %s", exc)
            return []

    def _retrieve_local(self, query: str, limit: int) -> str:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return ""

        scored: List[tuple] = []
        for doc in self._load_local_kb():
            title = doc.get("title", "")
            tags = doc.get("tags", [])
            content = doc.get("content", "")
            title_tokens = set(_tokenize(title))
            tag_tokens = set(_tokenize(" ".join(tags)))
            content_tokens = set(_tokenize(content))

            score = 0.0
            score += _LOCAL_SCORE_WEIGHT_TITLE * len(query_tokens & title_tokens)
            score += _LOCAL_SCORE_WEIGHT_TAGS * len(query_tokens & tag_tokens)
            score += len(query_tokens & content_tokens)
            # 整句包含度加权（查询串直接出现在正文中 -> 强命中）
            if query.lower() in content.lower():
                score += len(query_tokens) * 2
            if query.lower() in title.lower():
                score += len(query_tokens) * 2
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [doc for _, doc in scored[:limit]]
        return "\n\n".join(
            f"[{doc.get('title', '未命名')}] {doc.get('content', '')}" for doc in top
        )

    # ---------- 火山知识库（VikingDB） ----------
    async def _retrieve_vikingdb(self, query: str, limit: int) -> str:
        if not settings.KB_ACCOUNT_ID or not settings.KB_COLLECTION:
            logger.warning("KB_MODE=vikingdb 但缺少 KB_ACCOUNT_ID / KB_COLLECTION，请检查 .env")
            return ""

        host = settings.KB_HOST
        path = "/api/knowledge/collection/search_knowledge"
        body: Dict[str, Any] = {
            "project": settings.KB_PROJECT,
            "name": settings.KB_COLLECTION,
            "query": query,
            "limit": limit,
            "pre_processing": {
                "need_instruction": True,
                "return_token_usage": True,
                "messages": [{"role": "user", "content": query}],
            },
            "post_processing": {"get_attachment_link": True},
        }
        base_headers = {
            "Host": host,
            "Content-Type": "application/json",
            "V-Account-Id": settings.KB_ACCOUNT_ID,
        }
        signed = sign_request(
            access_key_id=settings.VOLC_ACCESS_KEY,
            secret_key=settings.VOLC_SECRET_KEY,
            service=settings.KB_SERVICE,
            region=settings.KB_REGION,
            method="POST",
            path=path,
            params={},
            headers=base_headers,
            body=body,
        )
        headers = {**base_headers, **signed["headers"]}
        url = f"{settings.KB_SCHEME}://{host}{path}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, content=signed["body"])
        except httpx.HTTPError as exc:
            logger.warning("知识库请求失败: %s", exc)
            return ""

        if response.status_code != 200:
            logger.warning("知识库请求非 200: %s %s", response.status_code, response.text[:200])
            return ""

        try:
            data = response.json()
        except ValueError:
            return ""

        result_list = ((data.get("data") or {}).get("result_list")) or []
        contents = [item.get("content", "") for item in result_list if item.get("content")]
        if not contents:
            logger.info("知识库未检索到相关内容: %s", query)
            return ""
        return "\n\n".join(contents)


rag_service = RagService()
