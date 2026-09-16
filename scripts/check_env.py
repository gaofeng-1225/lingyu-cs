#!/usr/bin/env python3
"""
环境自检脚本
============
用法：python scripts/check_env.py
读取 server/.env，逐项检查关键配置是否就绪，并给出缺失时的处理指引。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "server" / ".env"

REQUIRED = [
    ("VOLC_ACCESS_KEY", "火山引擎 AK", "https://console.volcengine.com/iam/keymanage"),
    ("VOLC_SECRET_KEY", "火山引擎 SK", "https://console.volcengine.com/iam/keymanage"),
    ("RTC_APP_ID", "RTC 应用 ID", "https://console.volcengine.com/rtc/aigc/listRTC"),
    ("RTC_APP_KEY", "RTC 应用 Key", "https://console.volcengine.com/rtc/aigc/listRTC"),
    ("ARK_API_KEY", "方舟 API Key", "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey"),
]

OPTIONAL = [
    ("ARK_ENDPOINT_ID", "方舟推理接入点（与 LLM_MODEL 二选一）", "https://console.volcengine.com/ark -> 在线推理 -> 创建推理接入点"),
    ("LLM_MODEL", "模型名（与 ARK_ENDPOINT_ID 二选一）", "如 doubao-seed-1-6-flash-250828"),
    ("SERVER_URL", "本服务公网地址（RTC 联调必需）", "ngrok http 3001 后填写 https 地址"),
    ("TTS_VOICE_TYPE", "TTS 音色（可选，默认官方音色）", "https://console.volcengine.com/ark/region:ark+cn-beijing/experience/voice"),
]


def load_env() -> dict:
    env: dict = {}
    if not ENV_PATH.exists():
        print(f"⚠️  未找到 {ENV_PATH}，请先复制 server/.env.example 为 server/.env")
        return env
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def main() -> int:
    env = load_env()
    if not env:
        return 1

    print("=" * 62)
    print("聆语智服 · 环境自检")
    print("=" * 62)
    ok = True

    print("\n【必填项】")
    for key, label, guide in REQUIRED:
        value = env.get(key, "")
        ready = bool(value) and value not in ("xxx", "xxxx")
        ok = ok and ready
        status = "✅ 已配置" if ready else "❌ 缺失"
        print(f"  {status}  {label:<16} ({key})")
        if not ready:
            print(f"         获取方式: {guide}")

    print("\n【二选一/可选项】")
    for key, label, guide in OPTIONAL:
        value = env.get(key, "")
        ready = bool(value)
        status = "✅ 已配置" if ready else "○ 未配置"
        print(f"  {status}  {label:<20} ({key})")
        if not ready and key in ("ARK_ENDPOINT_ID", "LLM_MODEL"):
            print(f"         获取方式: {guide}")

    # 特殊检查
    print("\n【组合检查】")
    model_ok = bool(env.get("ARK_ENDPOINT_ID") or env.get("LLM_MODEL"))
    print(f"  {'✅' if model_ok else '❌'}  大模型已指定（ARK_ENDPOINT_ID 或 LLM_MODEL 至少一个）")
    ok = ok and model_ok

    kb_mode = env.get("KB_MODE", "local")
    if kb_mode == "vikingdb":
        kb_ok = bool(env.get("KB_ACCOUNT_ID") and env.get("KB_COLLECTION"))
        print(f"  {'✅' if kb_ok else '❌'}  KB_MODE=vikingdb 已配置集合与账号 ID")
        ok = ok and kb_ok
    else:
        print(f"  ✅  KB_MODE=local（本地知识库联调模式，无需火山知识库账号）")

    print("\n" + "=" * 62)
    if ok:
        print("全部关键配置就绪 ✅  可以启动服务：cd server && python run.py")
    else:
        print("存在缺失配置 ❌  请按上方指引补齐 server/.env 后重试")
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
