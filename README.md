<div align="center">

# 今日人格卡 DoodleToday

**把你今天的三个状态，变成一张有设计感的专属人格卡**

<p>
  <img src="https://img.shields.io/badge/Node.js-22.12%2B-339933?logo=node.js&logoColor=white" alt="Node.js 22.12+">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/前端-React%2019%20%2B%20Vite-149eca" alt="React 19 + Vite">
  <img src="https://img.shields.io/badge/后端-FastAPI-05998b" alt="FastAPI">
  <a href="LICENSE"><img src="https://img.shields.io/badge/%E8%AE%B8%E5%8F%AF%E8%AF%81-MIT-0f766e" alt="许可证：MIT"></a>
</p>

**输入三个状态 · 选一款风格 · AI 写文案排版，本地渲染出 1080×1440 专属人格卡**

[快速开始](#快速开始) · [怎么用](#怎么用) · [能做什么](#能做什么) · [常见问题](#常见问题)

</div>

---

## 今日人格卡是什么

每天的状态和心情，说完就散了。今日人格卡是一个**轻量创作 Agent**：你输入今天的三个状态，再挑一种表达方式，它就调用 AI 帮你写文案、排版，生成一张可以分享、可以收藏的专属人格卡——像一张杂志封面、一张复古票据，或一页涂鸦手账。

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>🎨 八款风格</h3>
      杂志封面、趣味标签、简洁海报、复古票据、涂鸦手账、夜航霓虹、柔焦日记、数字档案。最新选定的一款优先。
    </td>
    <td width="33%" valign="top">
      <h3>✍️ 两种改稿</h3>
      用大白话让 AI 重写，或自己动手改标题、副标题、标签。每次成功渲染都是一个独立版本，随时预览、下载任意一版。
    </td>
    <td width="33%" valign="top">
      <h3>🛡️ 不替你决定</h3>
      只有点击"记住这个风格"才保存偏好，可随时清除。当天的状态不会沉淀成长期人格标签。
    </td>
  </tr>
</table>

**你可以用它：**

- 把"今天的我"生成一张卡，发给朋友，或收进作品库
- 生成后觉得文案不对味，一句话让 AI 改，或直接上手改字
- 上传一本照片回忆册，自动识别照片里的文字、核对后排版成册（需开启 OCR，见下文）

---

## 快速开始

> **适用环境：** Node.js 22.12+（已在 Node 24 验证）、Python 3.10+。macOS / Linux 均可。

**① 初始化（只需一次）**：克隆后运行：

```bash
python3 scripts/setup.py
```

它会装好 Python 虚拟环境和前端依赖、生成本项目专用的邀请口令和渲染凭据、构建前端。需要照片回忆册的 OCR 功能时，改用 `python3 scripts/setup.py --ocr`。

**② 启动**：

```bash
npm start
```

看到 `今日人格卡 → http://127.0.0.1:…` 后，用浏览器打开终端里打印的地址，输入 `.env` 中的 `INVITE_CODE` 即可开始创作。

**③（可选）接入真实模型**：编辑 `.env`，填入 `MODEL_BASE_URL`（以 `/v1` 结尾的 Chat Completions 兼容地址）、`MODEL_API_KEY`、`MODEL_ID`：

```bash
.venv/bin/python scripts/check_model.py   # 先做一笔小额真实验证
npm start                                  # 验证通过后重启生效
```

成功标准：页面能打开、输入口令能进入，生成人格卡能拿到真实的 1080×1440 PNG。

<details>
<summary><b>不配置模型能用吗？</b></summary>

<br>

能，但能力有限。未配置模型时，人格卡生成和 AI 改稿会**明确返回"不可用"（503）**，不会用固定文案冒充模型输出。此时回忆册仍可上传和人工核对，已生成的作品也可以直接改文案并重新渲染。

</details>

<details>
<summary><b>想在开发时改代码？</b></summary>

<br>

用 `npm run dev`，地址 http://127.0.0.1:5101，前端热更新并代理同源 API。注意同一项目不要同时跑 `npm start` 和 `npm run dev`。`Ctrl+C` 停止服务；任务持久化，重启后自动恢复。API 只运行一个 worker，不要加 `--workers`。

</details>

---

## 怎么用

打开页面后，整个创作流程只有四步：

| 步骤 | 做什么 |
| ---- | ------ |
| ① 输入状态 | 写下今天的三个状态，可选再补一句今天的经历 |
| ② 选风格 | 八款风格里挑一款，看实时预览选最对味的那张 |
| ③ 改稿 | 用大白话让 AI 改（"标题再丧一点，标签换成食物梗"），或直接编辑标题、副标题、标签后重新渲染 |
| ④ 下载 | 预览的是实际 PNG，点下载保存；作品库随时找回 |

Agent 每次最多和模型对话 8 轮，只调用白名单内的工具；它判断完成了就会停下，你只看结果，不满意接着追问。

渲染在**本地**完成（Satori + resvg，内部端口 3101），使用中文字体随项目提供，不访问字体 CDN，也禁止引用外部图片链接。

---

## 能做什么

| 功能 | 需要什么 |
| ---- | -------- |
| ✅ 人格卡生成、AI 改稿、版本管理、作品库、下载 | 配置模型后可用 |
| ✅ 手动改文案并重新渲染已有作品 | 不配置模型也可用 |
| ✅ 回忆册上传与人工核对 | 不需要模型 |
| 🧩 回忆册自动编排（照片 OCR 识别 + 排版） | `OCR_ENABLED=true`，并用 `setup.py --ocr` 安装 OCR 依赖 |

**额度：** 每个身份每天 20 次生成、改稿或直接重渲染，失败重试也计入额度；上传和 OCR 不计。

**模型要求：** 兼容 Chat Completions 协议（`{MODEL_BASE_URL}/chat/completions`），Bearer 认证，支持 function tools；要用云端图片理解还需支持 `image_url`。可选备用模型 `MODEL_FALLBACK_ID`，在主模型失败时自动降级。

---

## 常见问题

<details>
<summary><b>点生成提示"不可用"（503）？</b></summary>

<br>

说明模型还没配置或配置不对。检查 `.env` 里的 `MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_ID`，然后运行 `.venv/bin/python scripts/check_model.py` 做小额真实验证，通过后再重启。

</details>

<details>
<summary><b>我的数据存在哪？</b></summary>

<br>

全部在本项目的 `data/` 目录（SQLite、素材、版本文件），不提交到版本库，随项目一起备份或删除。不同项目之间的数据、口令、端口、依赖、进程互相独立。

</details>

<details>
<summary><b>它会记录什么？</b></summary>

<br>

数字轨迹只记录任务耗时、token 用量、工具失败次数、页面数和下载请求数——**不记录**提示词、原始票面、参数、模型响应或密钥。也不要开启 httpx / SDK 的 debug 日志。注意：下载请求数不能证明用户真的保存了图片，需结合 `docs/trial.csv` 的反馈判断。

</details>

<details>
<summary><b>公开上线前要注意什么？</b></summary>

<br>

1. 轻量会话挡不住主动清 Cookie 重新领身份，公开环境应改用**独立邀请账户**。
2. 每次 push 前运行 `npm run check:public`：扫描私有环境文件、本地数据目录、私钥、token、非占位密钥。克隆后启用一次版本化的 pre-push 钩子：

   ```sh
   git config core.hooksPath .githooks
   ```

   同样的检查也在 GitHub Actions 里对 push 和 PR 运行。真实模型密钥、服务器地址、邀请口令只放部署环境，**绝不提交**。

3. 没有域名想用手机内测？Compose 栈里的 `cloudflared` 容器会临时转发到本地服务，但生成的 `trycloudflare.com` 地址会随重启变化——公开上线前请换正式域名和受管的 Cloudflare Tunnel。

</details>

---

## 给开发者

<details>
<summary><b>架构、接口与测试</b></summary>

<br>

**关键文件**

| 文件 | 职责 |
| ---- | ---- |
| `frontend/src/main.tsx` / `style.css` | H5：核对/修改、版本、下载、作品库 |
| `backend/main.py` | 会话、配额、上传与业务 API |
| `backend/agent.py` | 最多 8 轮模型决策、白名单工具调用、程序完成判定 |
| `backend/tools.py` | 权限、来源、模板/偏好、原子版本写入 |
| `backend/provider.py` | 模型协议、45 秒超时、最多 2 次失败重试 |
| `backend/worker.py` / `db.py` | SQLite 持久任务、重启恢复、数字轨迹 |
| `backend/ocr.py` / `ocr_runner.py` | OCR 子进程、脱敏与候选字段 |
| `renderer/` | 本地内部渲染，端口 3101，静态中文字体 |

**接口：** 启动后访问 `/api/openapi.json` 获取完整 OpenAPI 定义。所有写请求需要 `X-Requested-With: studio`，登录后使用 HttpOnly Cookie。任务状态机：`queued → running → completed / awaiting_details / failed`；补问会创建新任务，旧任务变为 `superseded`。只有实际 PNG 合法且文本不越界，任务才算完成。

**测试与指标：**

```bash
.venv/bin/python -m pytest -q                    # 后端测试（隔离 SQLite + 模型替身）
npm run test:render                              # 渲染测试：三种模板、中文最大长度、文本边界、照片排版、禁外链
npm run build
.venv/bin/python scripts/export_metrics.py > docs/task-metrics.csv
```

测试调用真实 Node 渲染服务，不消耗模型费用。渲染测试的 20 组导出回归 ≠ 真实模型 90% 成功率的验收。

**设计依据：** [Satori](https://github.com/vercel/satori)、[resvg-js](https://github.com/thx/resvg-js)、[PaddleOCR](https://www.paddleocr.ai/main/en/quick_start.html)；Noto Sans SC（SIL OFL，许可证见 `renderer/fonts/OFL.txt`）。

</details>
