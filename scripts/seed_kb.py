#!/usr/bin/env python3
"""
知识库种子工具
==============
1. 本地模式（KB_MODE=local）：server/knowledge/kb_course.json 已内置样例知识库，
   直接替换该文件内容即可维护。

2. 火山模式（KB_MODE=vikingdb）：本脚本把样例知识库输出为 Markdown 文档
   （scripts/seed_kb.md），你在控制台上传该文档到知识库集合即可。

用法：python scripts/seed_kb.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_JSON = ROOT / "server" / "knowledge" / "kb_course.json"
OUT_MD = Path(__file__).resolve().parent / "seed_kb.md"

CONSOLE_URL = "https://console.volcengine.com/vikingdb/knowledge"


def main() -> None:
    data = json.loads(KB_JSON.read_text(encoding="utf-8"))
    docs = data.get("documents", [])

    print(f"本地知识库: {KB_JSON}")
    print(f"共 {len(docs)} 条文档\n")

    lines = ["# 聆语智服 · 样例知识库\n"]
    for doc in docs:
        lines.append(f"## {doc['title']}\n")
        lines.append(f"标签: {', '.join(doc.get('tags', []))}\n")
        lines.append(f"{doc['content']}\n")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成上传用 Markdown: {OUT_MD}\n")

    print("【切换为火山知识库（vikingdb）的步骤】")
    print(f"1. 打开 {CONSOLE_URL} 创建知识库集合（Collection）")
    print(f"2. 上传 {OUT_MD}（或你自己的业务文档）")
    print("3. 在 server/.env 中设置：")
    print("     KB_MODE=vikingdb")
    print("     KB_ACCOUNT_ID=<你的火山账号ID>")
    print("     KB_COLLECTION=<集合名称>")
    print("4. 重启服务，用 /debug/rag 验证检索效果")


if __name__ == "__main__":
    main()
