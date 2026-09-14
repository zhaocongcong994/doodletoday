# 今日人格卡 MVP 验收指南

## 启动

```bash
cd /Users/apple/AI/今日人格卡
npm start
```

打开 `http://127.0.0.1:8101`，使用项目 `.env` 中的 `INVITE_CODE` 登录。`Ctrl+C` 停止服务。

## 真实模型验收前配置

在本项目 `.env` 填入兼容 Chat Completions 工具调用的配置：

```dotenv
MODEL_BASE_URL=https://your-provider.example/v1
MODEL_ID=your-tool-capable-model
MODEL_API_KEY=your-private-key
```

先执行：

```bash
.venv/bin/python scripts/check_model.py
```

该命令只验证认证与工具调用，不打印密钥或服务商响应。未配置模型时，页面必须显示“创作模型暂未连接”；不能用固定文案替代生成结果。

## MVP 验收用例

1. 输入三个状态，例如“困 / 想出门 / 不想社交”，选择“杂志封面”，生成并下载 PNG。
2. 分别选择“趣味标签”和“简洁海报”，确认输出与第一种模板有明显差异。
3. 对已生成作品输入“只把副标题改短一点”，确认新版本产生，标题、标签和模板保持不变。
4. 在“直接修改文案”中修改副标题并保存，确认不调用模型也会产生可下载新版本。
5. 点击“记住这个风格”，新建作品时确认默认模板一致；点击“清除偏好”后确认偏好消失。
6. 刷新页面、停止并重启服务后，确认作品库、版本和下载仍可用。
7. 输入缺失状态或纯空白状态，确认页面阻止提交并说明原因。
8. 移除模型配置并重启，确认已有作品能预览、手工编辑和下载，但生成与 AI 改稿明确不可用。

## 发布前门槛

- `.venv/bin/python -m pytest -q`
- `npm run test:render`
- `npm run build`
- 真实模型使用 `docs/样例清单.json` 完成 20 组场景；至少 18 组产出合法 PNG。
- 真实模型结果不得出现心理诊断、科学人格结论或无依据的用户经历。

测试中的注入模型替身仅用于验证 Agent Loop、权限和渲染契约，不计入真实模型通过率。
