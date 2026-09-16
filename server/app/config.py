"""
聆语智服 LingYu · 全局配置
==========================
所有可调参数统一从 .env 读取（server/.env，参照 .env.example 创建）。
配置缺失时给出明确的引导信息，避免“跑不通不知道缺什么”。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

# 项目根目录（server/）
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


class Settings:
    # ---------- 服务基础 ----------
    APP_NAME: str = "聆语智服 LingYu · AI 语音智能客服"
    APP_VERSION: str = "0.1.0"
    HOST: str = _env("HOST", "0.0.0.0")
    PORT: int = int(_env("PORT", "3001"))

    # ---------- 火山引擎账号凭证（必填） ----------
    VOLC_ACCESS_KEY: str = _env("VOLC_ACCESS_KEY")
    VOLC_SECRET_KEY: str = _env("VOLC_SECRET_KEY")

    # ---------- 方舟 ARK 大模型 ----------
    ARK_BASE_URL: str = _env("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    ARK_API_KEY: str = _env("ARK_API_KEY")
    # 模型优先使用推理接入点 ID（ep-xxx）；也可直接填模型名（如 doubao-seed-1-6-flash-250828）
    ARK_ENDPOINT_ID: str = _env("ARK_ENDPOINT_ID")
    LLM_MODEL: str = _env("LLM_MODEL", "")
    LLM_TEMPERATURE: float = float(_env("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_TOKENS: int = int(_env("LLM_MAX_TOKENS", "300"))
    # 送入 LLM 的历史轮数（语音场景不宜过长）
    LLM_HISTORY_LENGTH: int = int(_env("LLM_HISTORY_LENGTH", "6"))

    # ---------- RTC（实时音视频） ----------
    RTC_APP_ID: str = _env("RTC_APP_ID")
    RTC_APP_KEY: str = _env("RTC_APP_KEY")
    RTC_BUSINESS_ID: str = _env("RTC_BUSINESS_ID", "")
    RTC_API_VERSION: str = _env("RTC_API_VERSION", "2024-12-01")
    RTC_ENDPOINT: str = _env("RTC_ENDPOINT", "https://rtc.volcengineapi.com")
    RTC_REGION: str = _env("RTC_REGION", "cn-north-1")

    # 本服务对外可达地址（RTC 云端回调必须能访问到，开发用 ngrok 等内网穿透）
    SERVER_URL: str = _env("SERVER_URL", "")

    # ---------- 知识库（VikingDB / 本地模式） ----------
    # vikingdb: 真实火山知识库检索；local: 本地 JSON 知识库（无需账号即可联调）
    KB_MODE: str = _env("KB_MODE", "local")
    KB_PROJECT: str = _env("KB_PROJECT", "default")
    KB_COLLECTION: str = _env("KB_COLLECTION", "")
    KB_ACCOUNT_ID: str = _env("KB_ACCOUNT_ID", "")
    KB_HOST: str = _env("KB_HOST", "api-knowledgebase.mlp.cn-beijing.volces.com")
    KB_SCHEME: str = _env("KB_SCHEME", "http")
    KB_REGION: str = _env("KB_REGION", "cn-north-1")
    KB_SERVICE: str = _env("KB_SERVICE", "air")
    KB_LIMIT: int = int(_env("KB_LIMIT", "3"))
    # 本地知识库文件路径（KB_MODE=local 时生效）
    KB_LOCAL_FILE: str = _env("KB_LOCAL_FILE", str(BASE_DIR / "knowledge" / "kb_course.json"))

    # ---------- 会话与日志 ----------
    DB_PATH: str = _env("DB_PATH", str(BASE_DIR / "data" / "lingyu.db"))

    # ---------- 内容安全 ----------
    SENSITIVE_WORDS: List[str] = [
        w.strip()
        for w in _env(
            "SENSITIVE_WORDS",
            "割韭菜,外包,包过,保过,交钱包过,百分百就业",
        ).split(",")
        if w.strip()
    ]
    # 命中敏感词后的兜底话术
    SENSITIVE_REPLY: str = _env(
        "SENSITIVE_REPLY",
        "这个话题我这边不太方便展开，您可以换个问题，或者留下联系方式由人工顾问为您解答。",
    )

    # ---------- AI 人设（可被 .env 覆盖） ----------
    SYSTEM_PROMPT: str = _env(
        "SYSTEM_PROMPT",
        """# 角色
你是【聆聆】，聆语智服平台的 AI 语音客服助手，负责接待课程咨询、售后支持与常见问题解答。

# 语音对话要求（重要）
- 你正在进行语音通话，回复必须简短、口语化，单次回答不超过 100 字，控制在 3 行以内。
- 不要使用列表、表格、代码块或 Markdown 符号。
- 语气自然热情，像一位靠谱的真人顾问。

# 回答规则
- 严格依据【参考知识库】回答，禁止编造价格、时间、政策等信息。
- 知识库中有相关内容：直接给出简洁准确的回答。
- 知识库中查不到：回复“抱歉，这个问题我暂时还不清楚，建议您留下联系方式，稍后由人工顾问为您详细解答。”
- 用户闲聊：可以友好回应，但尽快引导回正题。""",
    )

    # 语音场景：回复不超过 max_tokens，防止被截断导致播报中断
    @property
    def effective_model(self) -> str:
        return self.LLM_MODEL or self.ARK_ENDPOINT_ID

    @property
    def callback_url(self) -> str:
        return f"{self.SERVER_URL.rstrip('/')}/api/chat_callback"

    def missing_required(self) -> Dict[str, bool]:
        """返回关键配置缺失清单，便于环境自检。"""
        return {
            "VOLC_ACCESS_KEY / VOLC_SECRET_KEY": bool(self.VOLC_ACCESS_KEY and self.VOLC_SECRET_KEY),
            "RTC_APP_ID / RTC_APP_KEY": bool(self.RTC_APP_ID and self.RTC_APP_KEY),
            "ARK_API_KEY": bool(self.ARK_API_KEY),
            "ARK_ENDPOINT_ID 或 LLM_MODEL": bool(self.effective_model),
            "SERVER_URL（RTC 联调必需）": bool(self.SERVER_URL),
            "知识库配置（KB_MODE=vikingdb 时必需）": (
                self.KB_MODE == "local" or bool(self.KB_ACCOUNT_ID and self.KB_COLLECTION)
            ),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
