# GAIA LangGraph Agent

这是一个基于 LangGraph 的 GAIA Level 1 问答智能体项目，来自 Hugging Face Agents Course Final Assignment 的学习实践。

项目目标不是追求满分，而是完整走通一个 Agent 项目的基本工程闭环：

- 构建 ReAct 风格的 LangGraph Agent
- 为 Agent 接入搜索、网页抓取、文件解析等工具
- 批量运行 GAIA 题目并保存结果
- 调用课程评分 API 提交答案
- 使用 Chainlit 提供一个可视化聊天界面

当前一次正式提交结果：`8/20`，分数 `40%`，超过课程建议的 `30%` 目标。

## 项目状态

当前项目已经进入阶段性封版状态。

已经完成：

- LangGraph ReAct Agent 主流程
- GAIA 问题批量运行脚本
- GAIA 答案提交脚本
- Chainlit 可视化聊天入口
- 网页搜索与网页正文抓取
- GAIA 附件下载
- PDF / Excel / 图片 / 音频解析工具

暂不继续深入：

- YouTube 视频理解
- 更复杂的多 Agent 协作
- 更强的 planner / reviewer 架构
- 大规模重试、缓存和错误恢复系统

这些功能适合作为后续 Research Agent 或产品化 Agent 项目的第二阶段扩展。

## 项目结构

```text
build_my_gaia/
  myGAIAagent.py           # LangGraph Agent 主体和工具函数
  chat_ui.py               # Chainlit 可视化聊天入口
  run_gaia_questions.py    # 批量拉取并运行 GAIA 问题
  submit_gaia_answers.py   # 提交答案到课程评分 API

gaia_answers.json          # 已生成的答案结果
gaia_errors.json           # 运行失败或跳过的问题记录
gaia_files/                # GAIA 附件下载目录，本地生成
requirements.txt           # Python 依赖
README.md                  # 项目说明
.env                       # 本地环境变量，不要提交到公开仓库
```

## Agent 架构

`myGAIAagent.py` 中实现的是一个 ReAct 风格的 LangGraph Agent：

```text
START
  ↓
assistant
  ↓
tools_condition 判断是否需要工具
  ├─ 不需要工具 → END
  └─ 需要工具 → tools → assistant → ...
```

核心理解：

- `assistant` 节点负责调用大模型思考下一步。
- `tools` 节点负责真正执行工具函数。
- `tools_condition` 根据模型是否发起 tool call 决定下一步。
- `messages` 保存 HumanMessage、AIMessage、ToolMessage，形成当前任务的工作记忆。
- `add_messages` 的作用是追加消息，而不是覆盖旧消息。

## 当前工具

Agent 当前暴露给模型的工具包括：

- `calculator`：执行简单数学计算
- `read_text_file`：读取本地文本文件
- `download_gaia_file`：根据 `task_id` 下载 GAIA 附件
- `read_pdf_file`：读取 PDF 文本
- `read_excel_file`：读取 `.xlsx` 表格内容
- `analyze_image_file`：使用 Gemini 分析图片
- `transcribe_audio_file`：使用 Gemini 转写或分析音频
- `web_search`：使用 `ddgs` 进行网页搜索
- `fetch_webpage`：抓取网页正文文本

## 环境准备

建议使用 Python 虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

在项目根目录创建 `.env` 文件：

```text
GEMINI_API_KEY=你的 Gemini API Key
GAIA_AGENT_CODE_URL=https://huggingface.co/spaces/你的用户名/你的Space名/tree/main
```

注意：`.env` 只放在本地，不要提交到 GitHub 或公开仓库。

## 入口一：Chainlit 可视化聊天

这是平时手动测试 Agent 最方便的入口。

运行：

```powershell
chainlit run build_my_gaia/chat_ui.py -w
```

启动后浏览器访问：

```text
http://localhost:8000
```

适合用来测试：

- 普通问答
- 搜索能力
- 工具调用是否正常
- Agent 最终回答是否符合预期

如果问题涉及 GAIA 附件，需要在问题里提供 `task_id` 和文件名。例如：

```text
task_id 是 99c9cc74-fdc8-46c6-8f8d-3ce2d3bfeea3，文件名是 Strawberry pie.mp3。请根据音频回答题目。
```

## 入口二：批量运行 GAIA 问题

这是评测入口，用来从课程 API 拉取题目并批量运行 Agent。

运行：

```powershell
python build_my_gaia/run_gaia_questions.py
```

脚本会做这些事：

1. 请求 `GET /questions` 获取 20 道 GAIA 子集问题。
2. 逐题构造 `HumanMessage`。
3. 调用 `react_graph.invoke(...)`。
4. 将成功答案保存到 `gaia_answers.json`。
5. 将失败、跳过或超出循环限制的问题保存到 `gaia_errors.json`。

## 入口三：提交 GAIA 答案

确认 `gaia_answers.json` 中的答案可以提交后，运行：

```powershell
python build_my_gaia/submit_gaia_answers.py
```

提交脚本会读取：

- `.env` 中的 `GAIA_AGENT_CODE_URL`
- 本地的 `gaia_answers.json`

然后请求课程评分 API：

```text
POST https://agents-course-unit4-scoring.hf.space/submit
```

提交成功后会返回类似结果：

```json
{
  "username": "shabriri615",
  "score": 40.0,
  "correct_count": 8,
  "total_attempted": 8
}
```

## 开发流程建议

这个项目当前推荐的开发流程是：

1. 先用 Chainlit 手动测试单个问题。
2. 确认工具和回答逻辑没问题后，再跑 `run_gaia_questions.py`。
3. 检查 `gaia_answers.json` 和 `gaia_errors.json`。
4. 只在确认答案格式合理后运行 `submit_gaia_answers.py`。
5. 新增工具前先单独测试工具函数，再加入 `tools` 列表。

## 当前限制

- 搜索工具依赖外部网络，可能出现连接失败或限流。
- Gemini API 偶尔可能出现 SSL / ConnectError。
- 部分问题会触发 `GraphRecursionError`，说明 Agent 没有及时停止工具调用。
- YouTube 视频题目前没有实现自动理解。
- 当前项目偏学习用途，不是生产级服务。

## 后续学习方向

本项目封版后，建议继续学习：

- Docker：为 Chainlit Agent 编写 `Dockerfile` 和 `docker-compose.yml`
- Linux 基础：掌握 `cd`、`ls`、`grep`、`tail`、`curl`、`chmod` 等常用命令
- 多步 Workflow：单独实现一个 Research Agent，用 planner / searcher / writer 节点生成调研报告
- 工程化：日志、重试、缓存、配置管理、错误处理

