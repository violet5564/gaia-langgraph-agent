import json
from pathlib import Path

import requests
from langchain_core.messages import HumanMessage

from myGAIAagent import react_graph


# 课程方提供的评分 API 地址。
# 我们只是作为“客户端”去请求题目，不需要自己写 FastAPI 服务。
API_URL = "https://agents-course-unit4-scoring.hf.space"

# 为了调试方便，先不要一次跑完 20 题。
# 初学阶段建议从 3~5 题开始，看清楚每题为什么成功或失败。
MAX_QUESTIONS = 20

# LangGraph 的最大节点执行步数。
# ReAct agent 会在 assistant -> tools -> assistant 之间循环，太低会过早停止，太高会浪费 token。
RECURSION_LIMIT = 20

# 当前 agent 还不支持视频、音频、附件等复杂题。
# 先跳过这些题，避免把“工具不够”误判成“graph 写错”。
SKIP_UNSUPPORTED = True

# 成功答案和失败记录分别保存，方便之后复盘和提交。
ANSWERS_PATH = Path("gaia_answers.json")
ERRORS_PATH = Path("gaia_errors.json")


def get_questions() -> list[dict]:
    """从课程 API 拉取 GAIA 子集题目。"""
    response = requests.get(f"{API_URL}/questions", timeout=30)

    # 如果 API 返回 404/500 等错误，这里会直接抛异常，避免后面用坏数据继续跑。
    response.raise_for_status()
    return response.json()


def should_skip(question: str, file_name: str | None = None) -> tuple[bool, str]:
    """判断当前题目是否超出当前 agent 的工具能力。"""
    lowered_question = question.lower()

    # 这些关键词通常意味着需要视频理解工具。
    # 当前版本还没有 YouTube/视频工具，所以先跳过。
    unsupported_keywords = [
        "youtube.com",
        "youtu.be",
        "video",
    ]

    # 如果题目带附件，现在不再直接跳过。
    # agent 已经有 download_gaia_file 工具，可以先把附件下载到本地。

    for keyword in unsupported_keywords:
        if keyword in lowered_question:
            return True, f"unsupported keyword: {keyword}"

    return False, ""


def extract_text_content(content) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()

    return str(content).strip()


def build_agent_question(question: str, task_id: str, file_name: str | None = None) -> str:
    """把 task_id 和附件名一起交给 agent，方便它调用文件下载工具。"""
    if not file_name:
        return question

    return (
        f"Task ID: {task_id}\n"
        f"Attached file name: {file_name}\n\n"
        f"Question:\n{question}"
    )


def run_agent(question: str, task_id: str, file_name: str | None = None) -> str:
    """把一道 GAIA 问题交给 LangGraph agent，并取最后一条消息作为答案。"""
    result = react_graph.invoke(
        # graph 的输入必须符合 AgentState：这里就是 messages 字段。
        {"messages": [HumanMessage(content=build_agent_question(question, task_id, file_name))]},
        config={"recursion_limit": RECURSION_LIMIT},
    )

    # LangGraph 会保存完整消息历史；最后一条通常是 agent 的最终回答。
    # return str(result["messages"][-1].content).strip()
    return extract_text_content(result["messages"][-1].content)




def save_json(path: Path, data: list[dict]) -> None:
    """把中间结果保存到本地，避免程序中途失败后结果丢失。"""
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    
    # 1. 先拿到题目列表。
    questions = get_questions()

    # 2. 只取前 MAX_QUESTIONS 道，方便小批量调试。
    selected_questions = questions[:MAX_QUESTIONS]

    # answers 是以后提交 /submit 需要的核心数据。
    answers = []

    # errors 用来记录跳过/失败的题，帮助我们判断下一阶段该补什么工具。
    errors = []

    print(f"Loaded {len(questions)} questions")
    print(f"Running {len(selected_questions)} questions")

    for index, item in enumerate(selected_questions, start=1):
        # 每道题至少有 task_id 和 question。
        # file_name 可能不存在，所以用 get。
        task_id = item["task_id"]
        question = item["question"]
        file_name = item.get("file_name")

        print("=" * 80)
        print(f"Question {index}/{len(selected_questions)}")
        print("Task ID:", task_id)
        print("Question:", question)

        # 3. 先判断当前工具能不能处理这类题。
        # 这一步不是偷懒，而是为了建立清晰的能力边界。
        skip, reason = should_skip(question, file_name)
        if SKIP_UNSUPPORTED and skip:
            print("Skipped:", reason)
            errors.append(
                {
                    "task_id": task_id,
                    "question": question,
                    "error_type": "skipped",
                    "error": reason,
                }
            )
            continue

        try:
            # 4. 真正调用 agent 回答问题。
            submitted_answer = run_agent(question, task_id, file_name)
            print("Answer:", submitted_answer)

            # 这个格式接近课程提交 API 需要的 answers 格式。
            answers.append(
                {
                    "task_id": task_id,
                    # "question": question, # 这个字段不是提交 API 要的，但我们保留它方便复盘。
                    "submitted_answer": submitted_answer,
                }
            )
        except Exception as error:
            # 单题失败不要让整个批量任务停止。
            # 比如网络错误、recursion limit、工具异常，都记录下来继续下一题。
            print("Agent run failed:", error)
            errors.append(
                {
                    "task_id": task_id,
                    # "question": question,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

        # 5. 每跑完一道题就保存一次。
        # 这样即使第 4 题崩了，前 3 题结果也还在。
        save_json(ANSWERS_PATH, answers)
        save_json(ERRORS_PATH, errors)

    # 循环结束后再保存一次，确保最终文件是最新的。
    save_json(ANSWERS_PATH, answers)
    save_json(ERRORS_PATH, errors)
    print("=" * 80)
    print(f"Saved {len(answers)} answers to {ANSWERS_PATH}")
    print(f"Saved {len(errors)} errors to {ERRORS_PATH}")


if __name__ == "__main__":
    main()
