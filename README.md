# DoodleToday

独立运行的 React / TypeScript + FastAPI + Satori/resvg 轻量创作 Agent。方案已确认并实现；真实模型服务商、模型 ID 和凭据尚未配置。未配置时明确显示不可用，没有以固定文案冒充模型的运行模式。前台排版示例由本地模板生成，测试使用注入的模型替身。

## 启动

依赖：Node.js 22.12+（本机验证 Node 24）、Python 3.10+。


当前工作区已初始化依赖和独立 `.env`，可直接 `npm start`。开发模式 `npm run dev` 使用 http://127.0.0.1:5101 并代理同源 API。同一项目不能同时启动 start 与 dev。

初始化脚本为本项目生成邀请口令 `INVITE_CODE` 和内部 `RENDER_TOKEN`，保存在权限为 600 的 `.env`。在本机编辑器中查看口令。30 天浏览器会话绑定独立身份；清除 Cookie、换浏览器或会话过期后，旧作品不会自动关联回来。内测需要保留同一浏览器。

`Ctrl+C` 停止服务；任务持久化，重启恢复。每项目只能运行一个 API worker，不要加 `--workers`。两项目的数据、口令、端口、依赖、进程互不依赖。

服务地址需兼容 Chat Completions：向 `MODEL_BASE_URL/chat/completions` 发送请求，使用 Bearer 认证和 function tools。当前只有这个协议适配器，不宣称支持所有供应商的原生 API。可选云端图片理解还要求同一模型支持 `image_url`。配置后执行小额真实验证，再重启：

```bash
.venv/bin/python scripts/check_model.py
```

未配置时人格卡生成/AI 改稿返回 503；回忆册可上传与核对，但自动编排不可用。已经生成的作品仍可直接改文案并重新渲染。

## 创作流程

1. 输入三个状态，可选一句经历，选择八款表达风格之一：杂志封面、趣味标签、简洁海报、复古票据、涂鸦手账、夜航霓虹、柔焦日记或数字档案。
2. Agent 读取显式风格偏好并渲染第一版，最新选定风格优先。
3. 输入改稿要求，或直接改标题、副标题、标签。每次成功渲染创建独立版本。
4. 预览展示实际 1080×1440 PNG，点击下载保存。
5. 只有点击“记住这个风格”才保存偏好，可随时清除。当日状态不沉淀为长期人格标签。

## 文件与接口

| 文件 | 职责 |
|---|---|
| `frontend/src/main.tsx` / `style.css` | H5、核对/修改、版本、下载、作品库 |
| `backend/main.py` | 会话、配额、上传与业务 API |
| `backend/agent.py` | 最多 8 轮模型决策、白名单工具调用、程序完成判定 |
| `backend/tools.py` | 权限、来源、模板/偏好、原子版本写入 |
| `backend/provider.py` | 模型协议、45 秒超时、最多 2 次失败重试 |
| `backend/worker.py` / `db.py` | SQLite 持久任务、重启恢复、数字轨迹 |
| `backend/ocr.py` / `ocr_runner.py` | OCR 子进程、脱敏与候选字段 |
| `renderer/` | 本地内部渲染，端口 3101，静态中文字体 |
| `data/` | 私有 SQLite、素材、版本，不提交到版本库 |
| `docs/` | 需求架构、计划、验收记录、试用指标 |

启动后 `/api/openapi.json` 提供完整 OpenAPI 接口定义。所有写请求需要 `X-Requested-With: studio`，登录后需要 HttpOnly Cookie；接口按项目类型限制。

- `POST/GET /api/session`、`GET /api/health`
- `GET /api/works`、`GET/DELETE /api/works/{id}`
- `POST /api/cards`、`POST /api/works/{id}/revise`、`POST /api/works/{id}/card-content`
- `PUT/DELETE /api/preferences`
- `POST /api/albums`（multipart）、`POST /api/works/{id}/details`、`POST /api/works/{id}/album-content`
- `GET /api/tasks/{id}`、`POST /api/tasks/{id}/retry`
- `GET /api/works/{id}/assets/{assetId}`
- `GET /api/works/{id}/versions/{versionId}/{filename}?download=true`

状态：`queued → running → completed / awaiting_details / failed`。回答补问创建新任务，旧任务变为 `superseded`。同一作品处理时不接受第二次写入/删除。只有实际 PNG 合法且文本不越界才完成。每身份每天 20 次生成、改稿或直接重渲染，重试计入额度；上传/OCR 不计。轻量会话不能防止主动清 Cookie 重新领身份，公开上线前应采用独立邀请账户。

## 测试与指标

```bash
.venv/bin/python -m pytest -q
npm run test:render
npm run build
.venv/bin/python scripts/export_metrics.py > docs/task-metrics.csv
```

测试使用隔离 SQLite、人工构造素材和注入模型替身，调用真实 Node 渲染服务，不消耗模型费用。每项目 20 组导出回归不等于真实模型的 90% 成功率验收。渲染测试涵盖三种模板、中文最大长度、文本边界、照片排版和禁止外部图片 URL。结果见 [验收记录](docs/验收记录.md)。

轨迹包括任务耗时、token、工具失败、页面数、下载请求，不记录提示词、原始票面、参数、模型响应或密钥。不要开启 httpx/SDK debug 日志。下载请求数不能证明保存成功，需结合 `docs/trial.csv` 的反馈。


## 设计依据

- [需求与七层架构](docs/需求与架构.md)、[开发计划](docs/开发计划.md)
- [Agent Blueprint](../agent-blueprint/BLUEPRINT.md)
- [Satori](https://github.com/vercel/satori)、[resvg-js](https://github.com/thx/resvg-js)、[PaddleOCR](https://www.paddleocr.ai/main/en/quick_start.html)
- Noto Sans SC，SIL OFL，许可证 `renderer/fonts/OFL.txt`。静态 TTF 随项目提供，渲染无需访问字体 CDN。
## Public repository safety

Before every public push, run `npm run check:public`. It scans the tracked tree
and staged files for private environment files, local data/build directories,
private-key material, recognizable access tokens, and non-placeholder secret
assignments. It does not replace revoking a secret that has already leaked.

This checkout also uses the versioned `.githooks/pre-push` hook. Enable it once
after cloning with:

```sh
git config core.hooksPath .githooks
```

The same check runs in GitHub Actions for pushes and pull requests. Real model
keys, server addresses, invitation credentials, and user data belong only in
the deployment environment, never in tracked files.
