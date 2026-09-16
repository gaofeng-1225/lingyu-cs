"""聆语智服 LingYu · FastAPI 应用入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .aicore.sessions import init_db
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("lingyu")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("初始化数据库 %s", settings.DB_PATH)
    init_db()
    yield
    logger.info("服务关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "聆语智服 · AI 语音智能客服服务端\n\n"
        "- `getScenes` / `proxy`：业务网关（场景下发、RTC 入会、OpenAPI 代理）\n"
        "- `/api/chat_callback`：RTC 云端第三方大模型回调（RAG + 豆包流式）\n"
        "- `/debug/*`、`/api/v1/chat`：AI 调试台\n"
        "- `/api/call-logs`、`/api/voice-sessions`：运营日志\n\n"
        "联调前请先访问 `/api/env-check` 检查配置是否就绪。"
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 业务网关
from .gateway import proxy as gateway_proxy
from .gateway import scenes as gateway_scenes

# AI 中枢
from .aicore import callback as aicore_callback
from .aicore import chat as aicore_chat

app.include_router(gateway_scenes.router)
app.include_router(gateway_proxy.router)
app.include_router(aicore_callback.router)
app.include_router(aicore_chat.router)
