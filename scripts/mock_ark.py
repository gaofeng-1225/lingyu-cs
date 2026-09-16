"""本地冒烟测试：mock ARK + lingyu 服务端全链路验证。"""

import json
import threading
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

# ---------- mock ARK（OpenAI 兼容流式接口） ----------
mock_app = FastAPI()


@mock_app.post("/v3/chat/completions")
async def mock_chat(request: Request):
    body = await request.json()
    stream = body.get("stream", False)
    last = body["messages"][-1]["content"]
    reply = f"好的，根据知识库，AIGC 实战营学费是 3999 元（你说：{last[:20]}）。"
    if not stream:
        return {
            "choices": [{"message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 42},
        }

    def gen():
        for ch in reply:
            yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': ch}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
        yield "data: " + json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}) + "\n\n"
        yield "data: " + json.dumps({"usage": {"total_tokens": 42}}) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


def start_mock_ark() -> uvicorn.Server:
    config = uvicorn.Config(mock_app, host="127.0.0.1", port=8099, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    return server


if __name__ == "__main__":
    start_mock_ark()
    print("mock ARK started at 127.0.0.1:8099", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("mock ARK stopped")
