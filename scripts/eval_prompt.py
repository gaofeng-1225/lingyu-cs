#!/usr/bin/env python3
"""
LLM 批量评测脚本
================
用法：
  python scripts/eval_prompt.py                    # 使用默认评测集
  python scripts/eval_prompt.py --set my_eval.json # 指定评测集

评测集格式（JSON）：
[
  {"question": "AIGC 实战营多少钱？", "ideal": "3999 元，学制 3 个月，零基础可报。"},
  ...
]

流程：对每条问题调用当前配置的 ARK 模型 → 让 LLM 作为评委按 1~5 分
与理想答案对比打分 → 输出表格与平均分。修改提示词/换模型后重跑即可回归。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from app.config import settings  # noqa: E402
from app.aicore.llm import LLMError, llm_service  # noqa: E402
from app.aicore.prompt import build_messages  # noqa: E402

DEFAULT_SET = Path(__file__).resolve().parent / "eval_set.json"

JUDGE_PROMPT = """你是一名严格的智能客服评测专家。请对【AI 回答】进行打分（1-5 分）：
- 5分：信息完全正确且完整，包含理想答案全部关键信息
- 4分：信息正确，但遗漏少量次要信息
- 3分：信息基本正确，有少量偏差或遗漏
- 2分：信息有较大偏差或遗漏关键信息
- 1分：信息错误或完全无关

【理想答案】
{ideal}

【AI 回答】
{answer}

只输出 JSON：{{"score": 整数, "reason": "一句话理由"}}"""


async def evaluate(set_path: Path) -> None:
    items = json.loads(set_path.read_text(encoding="utf-8"))
    print(f"评测集: {set_path.name}，共 {len(items)} 条\n")

    results = []
    for i, item in enumerate(items, 1):
        question = item["question"]
        ideal = item["ideal"]
        print(f"[{i}/{len(items)}] {question}")

        # 1. 业务回答（走与线上一致的提示词编排，无知识库上下文）
        messages = build_messages([{"role": "user", "content": question}], rag_context="")
        try:
            answer = await llm_service.complete(messages)
        except LLMError as exc:
            print(f"    ❌ 调用失败: {exc}")
            continue

        # 2. LLM 评委打分
        judge_messages = [
            {"role": "system", "content": "你是评测助手。"},
            {"role": "user", "content": JUDGE_PROMPT.format(ideal=ideal, answer=answer)},
        ]
        try:
            judge_raw = await llm_service.complete(judge_messages)
            judge = json.loads(judge_raw.strip().strip("```json").strip("```"))
            score = int(judge.get("score", 0))
            reason = judge.get("reason", "")
        except Exception:
            score, reason = 0, "评委解析失败"

        results.append({"question": question, "answer": answer, "score": score, "reason": reason})
        print(f"    得分 {score}/5  {reason}")
        print(f"    回答: {answer[:60]}")

    if results:
        avg = sum(r["score"] for r in results) / len(results)
        print(f"\n{'='*50}")
        print(f"平均分: {avg:.2f} / 5（共 {len(results)} 条有效样本）")
        report = Path(__file__).resolve().parent / "eval_report.json"
        report.write_text(
            json.dumps({"avg_score": avg, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"明细已保存: {report}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM 批量评测")
    parser.add_argument("--set", type=Path, default=DEFAULT_SET, help="评测集 JSON 路径")
    args = parser.parse_args()

    if not args.set.exists():
        print(f"评测集不存在: {args.set}")
        sys.exit(1)
    asyncio.run(evaluate(args.set))


if __name__ == "__main__":
    main()
