<div align="center">

# AI 自动对诗平台 · PoetryDuel

**你出上句，AI 对下句 —— 对联 / 接龙 / 唱和 / 飞花令，四种玩法。**

[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](#)
[![Web](https://img.shields.io/badge/UI-Web%20%2B%20%E5%8F%A4%E5%85%B8%E6%B0%B4%E5%A2%A8%E9%A3%8E-2ea44f)](#)
[![Model](https://img.shields.io/badge/%E6%A8%A1%E5%9E%8B-%E4%BA%91%E7%AB%AF%20%2F%20%E6%9C%AC%E5%9C%B0%20Ollama%20%2F%20%E5%86%85%E7%BD%AE%E5%85%9C%E5%BA%95-EE4C2C)](#)
[![Offline](https://img.shields.io/badge/%E7%A6%BB%E7%BA%BF-%E5%86%85%E7%BD%AE%E7%A4%BA%E4%BE%8B%E5%85%9C%E5%BA%95-8957E5)](#)
[![Exe](https://img.shields.io/badge/%E5%8F%91%E5%B8%83-PyInstaller%20onefile-0078D6?logo=windows&logoColor=white)](#)

</div>

---

## 一句话

一个能真正陪你玩古诗的 Web 应用。四种玩法各有各的格律约束：
对联要平仄相对、接龙要尾字押韵、唱和要依原诗体、飞花令要含指定字。

**最难的是"不联网也能用"** —— 模型走三通道自动降级：
云端大模型 → 本地 Ollama → 内置示例兜底，断网也不会甩你一个错误框。

## 亮点

| | |
|---|---|
| **四种玩法** | 对联（平仄/词性/意境）、接龙（尾字押韵校验）、唱和（依原诗体响应一阕）、飞花令（优先内置诗词库检索经典名句） |
| **三通道自动切换** | 云端 → Ollama → 内置示例，任一条通就继续 |
| **流式输出** | AI 诗句逐字渲染，打字机效果 |
| **历史记录** | 存浏览器 localStorage，刷新不丢 |
| **隐私友好** | 无自动弹窗；API Key 以 Base64 加密存本地浏览器，不上传任何服务器 |
| **可打包** | `PoetryDuel.spec` → 单文件 exe，双击即用 |

## 30 秒上手

```powershell
python -m pip install --target libs -r requirements.txt
python start_server.py          # 默认 http://127.0.0.1:8000
```

配置项见 `.env.example`。

---

## 详细说明

一个 Web 版 AI 对诗应用：你出上句，AI 自动对诗回应。支持**对联、诗词接龙、唱和、飞花令**四种经典玩法，古典水墨风界面，云端大模型与本地模型自动切换。

## 功能

| 模式 | 玩法 | 说明 |
|------|------|------|
| 对联 | 出上联，对下联 | 平仄相对、词性对仗、意境契合，附韵律点评 |
| 接龙 | 出诗句，续下句 | 尾字押韵衔接，附押韵校验 |
| 唱和 | 出诗，回诗 | AI 依原诗诗体与风格回应一首 |
| 飞花令 | 出字，得句 | 优先内置诗词库检索经典名句，不足时 AI 创作 |

- **三通道自动切换**：云端大模型（优先）→ 本地 Ollama → 内置示例（离线兜底）
- **流式输出**：AI 诗句逐字渲染（打字机效果）
- **历史记录**：对话保存在浏览器 localStorage，刷新不丢
- **隐私友好**：无自动弹窗；API Key 以 Base64 加密存于本地浏览器

## 快速开始

```powershell
# 1. 安装依赖（已装可跳过）
python -m pip install --target libs -r requirements.txt

# 2. 启动（默认 http://127.0.0.1:8000）
python start_server.py
```

浏览器打开 <http://127.0.0.1:8000/> 即可使用。未配置任何模型时走"内置示例"通道，平台功能完整可玩。

> 依赖安装到项目内 `libs/` 目录（避免写入系统 Python 目录），启动脚本会自动加载；也可通过环境变量 `POETRY_DUEL_LIBS` 指定其他位置。

## 接入云端大模型

点击右上角 **⚙ 设置**，填入任意 OpenAI 兼容厂商的参数：

| 厂商 | base_url | 模型示例 |
|------|----------|----------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 阿里通义 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 豆包 | `https://ark.cn-beijing.volces.com/api/v3` | 你的推理接入点 ID |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |

也可以直接编辑项目根目录 `.env` 文件（`CLOUD_BASE_URL` / `CLOUD_API_KEY` / `CLOUD_MODEL`），重启生效。

## 接入本地模型（可选）

1. 安装 [Ollama](https://ollama.com/) 并拉取模型：`ollama pull qwen2.5:7b`
2. 确保 Ollama 运行（默认 `http://localhost:11434`，OpenAI 兼容端点为 `/v1`）
3. 平台自动探测本地可用性；云端不可用时自动降级本地

隐私敏感场景可在设置中勾选"强制使用本地模型"。

## API 一览

| 接口 | 说明 |
|------|------|
| `GET /api/health` | 云端/本地/示例通道状态 |
| `GET /api/modes` | 模式列表 |
| `POST /api/duel` | 非流式对诗 `{mode, content, force_local}` |
| `POST /api/duel/stream` | SSE 流式对诗（前端默认使用） |
| `POST /api/verify` | 韵律校验（字数/平仄/韵部） |

## 项目结构

```
poetry-duel-platform/
├── backend/
│   ├── main.py          # FastAPI 入口（路由 + SSE）
│   ├── ai_adapter.py    # 云端/本地/Mock 三通道自动切换
│   ├── poetry_modes.py  # 四模式处理逻辑
│   ├── prosody.py       # 韵律引擎（平仄/押韵/对仗）
│   ├── poem_db.py       # 诗词知识库检索
│   ├── prompts.py       # 提示词工程
│   └── config.py        # 配置加载（.env）
├── frontend/            # 古典水墨风前端（无框架）
├── data/poems.json      # 内置经典诗词（80+ 首）
├── start_server.py      # 启动脚本
└── requirements.txt
```

## 注意事项

- 内置诗词库约 80 余首经典作品，供飞花令优先检索；如需扩充，直接向 `data/poems.json` 追加条目即可。
- 韵律校验基于普通话拼音近似（平水韵/十三辙简化），供辅助点评，不替代专业诗词格律工具。
- API Key 仅存于本机浏览器 localStorage（Base64 加密），适合个人本地使用；多用户部署时建议改为服务端安全存储。
