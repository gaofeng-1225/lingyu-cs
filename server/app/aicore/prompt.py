"""
提示词编排（AI 中枢）
=====================
针对语音场景的 LLM 性能优化：
1. 系统提示词与 RAG 检索结果合并为【一条】 system 消息，
   触发方舟前缀缓存（Prefix Caching）与 KV Cache，显著降低首字延迟；
2. RAG 检索片段保持稳定顺序（按检索接口返回顺序，不做语义排序），
   避免缓存失效；
3. 会话历史带上最近 N 轮，同样利于前缀复用。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..config import settings

_RAG_BLOCK = "### 参考知识库（绝对准则）\n{context}"


def build_system_message(rag_context: str = "", extra_prompt: Optional[str] = None) -> str:
    """合并人设提示词与知识库上下文为单条 system 消息。"""
    blocks: List[str] = [extra_prompt or settings.SYSTEM_PROMPT]
    if rag_context.strip():
        blocks.append(_RAG_BLOCK.format(context=rag_context.strip()))
    return "\n\n".join(blocks)


def build_messages(
    history: List[Dict[str, str]],
    rag_context: str = "",
    extra_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """组装最终消息序列：system（人设+知识库） + 最近对话历史。"""
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": build_system_message(rag_context, extra_prompt)}
    ]
    messages.extend(history[-settings.LLM_HISTORY_LENGTH * 2 :])
    return messages
