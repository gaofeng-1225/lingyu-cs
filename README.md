# 聆语智服 LingYu · AI 语音智能客服系统

> 基于 **火山引擎 RTC（实时音视频）+ 豆包大模型（方舟 ARK）+ RAG 知识库** 的
> 实时语音智能客服项目。用户开口说话 → ASR 识别 → RAG 检索 → 大模型生成 →
> TTS 语音播报，全程毫秒级打断响应。

---

## 一、项目亮点

| 能力 | 说明 |
|---|---|
| 🎙️ 实时语音对话 | 火山 RTC 全双工低延迟（UDP），浏览器端 3A 音频处理（回声消除/降噪/增益），毫秒级打断 |
| 🧠 RAG 检索增强 | 双引擎知识库：火山 VikingDB（正式）+ 本地 JSON（免账号联调），回答严格基于知识库 |
| 💬 流式生成 | 豆包 SSE 流式输出，TTS 边收边播，首字延迟低 |
| 🎭 多场景配置化 | 场景 JSON 驱动（课程咨询 / 售后支持 / 通用助手），新增场景无需改代码 |
| 📊 会话与日志 | SQLite 持久化通话记录与日志（耗时 / Token / 敏感词），支撑运营复盘 |
| 🧪 AI 调试台 | Swagger UI + RAG/LLM/回调模拟接口，不启动 RTC 即可联调 |
| 📈 批量评测 | LLM-as-Judge 评测集打分，改提示词/换模型可回归对比 |
| 🛡️ 内容安全 | 敏感词拦截兜底话术，不进入大模型 |

## 二、技术架构

```
┌─────────────┐   HTTPS/WebSocket   ┌──────────────────┐
│   Web 前端   │ ──────────────────► │   业务网关 gateway │
│ React + RTC │  getScenes / proxy  │  FastAPI (3001)   │
└──────┬──────┘                     │  - 场景下发        │
       │ 加入 RTC 房间（音频流）       │  - RTC Token 签发  │
       ▼                            │  - OpenAPI 代理    │
┌──────────────────────────┐        └────────┬─────────┘
│ 火山引擎 RTC 云端（AIGC）  │  ASR 识别        │ StartVoiceChat
│  ASR → LLM → TTS        │ ◄───────────────┘
└──────────┬───────────────┘  回调 CustomLLM
           │ POST /api/chat_callback（SSE 流式）
           ▼
┌──────────────────────────┐
│   AI 中枢 aicore          │
│  - RAG 检索（VikingDB/本地）│
│  - 提示词编排（前缀缓存优化）  │
│  - 豆包流式生成（ARK）       │
│  - 会话/日志持久化（SQLite） │
└──────────────────────────┘
```

**一句话流程**：浏览器麦克风声音 → RTC 云端 ASR 转文字 → 回调到本服务 →
RAG 检索知识库 → 豆包生成回复（流式）→ 返回 RTC 云端 → TTS 合成语音推回房间 →
浏览器自动订阅播放，字幕与状态实时显示在界面上。

## 三、目录结构

```
lingyu-cs/
├── server/                  # 服务端（FastAPI，网关 + AI 中枢一体，可拆分微服务）
│   ├── app/
│   │   ├── gateway/         # 业务网关：场景下发 / RTC Token / OpenAPI 代理
│   │   ├── aicore/          # AI 中枢：回调 / RAG / LLM / 提示词 / 会话
│   │   └── utils/           # 火山 V4 签名
│   ├── scenes/              # 场景配置（JSON，支持 ${ENV} 引用）
│   ├── knowledge/           # 本地知识库（KB_MODE=local 时使用）
│   ├── data/                # SQLite 数据文件（运行时生成）
│   ├── .env.example         # 环境配置模板（复制为 .env 填写）
│   └── run.py               # 启动入口（热更新已排除缓存）
├── web/                     # 前端（React 18 + Vite + Redux Toolkit + @volcengine/rtc）
├── scripts/                 # 环境自检 / 批量评测 / 知识库种子 / mock ARK
└── docs/                    # 架构、配置清单、接口、面试亮点文档
```

## 四、快速开始

> 完整步骤见 [docs/02-配置清单与配合事项.md](docs/02-配置清单与配合事项.md)，
> 联调前请先跑 `python scripts/check_env.py` 自检。

### 1. 准备环境

```bash
# Python（建议 conda 独立环境）
conda create -n lingyu python=3.13
conda activate lingyu
pip install -r server/requirements.txt

# Node（建议用 nvm 管理，v18+ 即可）
nvm install 20
```

### 2. 配置 server/.env

```bash
cd server
cp .env.example .env
# 编辑 .env，填入火山引擎密钥（详见 docs/02）
```

### 3. 启动服务端

```bash
cd server
python run.py
# Swagger 调试台: http://127.0.0.1:3001/docs
# 环境自检:      http://127.0.0.1:3001/api/env-check
```

### 4. 启动前端

```bash
cd web
npm install --legacy-peer-deps
npm run dev
# 浏览器打开 http://127.0.0.1:5173
```

### 5. 内网穿透（RTC 联调必需）

```bash
ngrok config add-authtoken <你的TOKEN>
ngrok http 3001
# 把得到的 https://xxxx.ngrok-free.dev 填入 server/.env 的 SERVER_URL，重启服务
```

> ⚠️ 启动 Python 服务前，请先在火山 RTC 控制台「挂断」正在运行的通话房间，
> 否则会因房间冲突导致 StartVoiceChat 失败。

## 五、联调顺序（推荐）

1. **不依赖 RTC**：跑通 `/debug/rag`（知识库检索）与 `/debug/chat`（流式对话）
2. **模拟回调**：`/debug/callback` 用与 RTC 云端一致的协议跑完整链路
3. **真实通话**：前端点「开始通话」→ 授权麦克风 → 与 AI 语音对话 → 随时打断

## 六、常见问题

| 现象 | 排查 |
|---|---|
| `getScenes` 报错 | 服务端未启动 / `.env` 未配置 RTC_APP_ID |
| 点开始通话没反应 | 浏览器需 localhost 或 HTTPS；确认已授权麦克风 |
| 一直「AI 准备中」 | 服务未开通对应权限 / LLMConfig 回调地址不可达（ngrok 是否在跑） |
| StartVoiceChat 报房间冲突 | 控制台有房间未挂断；或同一会话重复启动 |
| 回调无反馈 | 用 `/debug/callback` 自测；确认 `SERVER_URL` 公网可达 |

## 七、授权说明

本仓库代码为原创实现，RTC 二进制消息协议与 OpenAPI 调用方式参考
[火山引擎 RTC-AIGC 官方 Demo](https://github.com/volcengine/rtc-aigc-demo)（BSD-3-Clause）与
[火山引擎官方文档](https://www.volcengine.com/docs/6348/1310537)，使用请遵守火山引擎服务条款。
