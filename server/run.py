"""
聆语智服 · 服务启动入口
========================
启动：python run.py（开发模式，热更新）
注意：热更新已排除 __pycache__ / .venv，避免编译缓存触发无谓重启。
"""

from __future__ import annotations

import uvicorn

from app.config import settings

if __name__ == "__main__":
    print(f"🚀 {settings.APP_NAME} 启动中: http://127.0.0.1:{settings.PORT}")
    print(f"   调试台 Swagger UI: http://127.0.0.1:{settings.PORT}/docs")
    print(f"   环境自检: http://127.0.0.1:{settings.PORT}/api/env-check")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=[".", "app"],
        reload_excludes=[
            "*/__pycache__/*",
            "*.pyc",
            ".venv/*",
            "*/.venv/*",
            "data/*",
        ],
    )
