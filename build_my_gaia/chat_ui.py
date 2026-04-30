"""Chainlit chat UI for the GAIA LangGraph agent.

运行方式：
    chainlit run build_my_gaia/chat_ui.py

这个文件只负责“界面层”：
1. 接收用户在网页聊天框里输入的问题。
2. 把问题包装成 LangChain 的 HumanMessage。
3. 调用 myGAIAagent.py 里已经写好的 react_graph。
4. 把 agent 的最后回答显示回 Chainlit 页面。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import chainlit as cl
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage


# 确保无论从项目根目录还是 build_my_gaia 目录启动，都能导入 myGAIAagent。
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

load_dotenv()

from myGAIAagent import react_graph  # noqa: E402


RECURSION_LIMIT = 20


def format_message_content(content: Any) -> str:
    """把不同模型可能返回的 content 统一转换成可显示的字符串。"""
    if isinstance(content, str):
        return content

    # Gemini / LangChain 有时会返回类似 [{'type': 'text', 'text': '...'}] 的列表。
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(str(item["text"]))
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts).strip()

    return str(content)


def get_last_ai_answer(messages: list[AnyMessage]) -> str:
    """从 graph 返回的 messages 中取最后一条 AIMessage 作为最终答案。"""
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return format_message_content(message.content)
    return "Agent did not return an AI answer."


@cl.on_chat_start
async def on_chat_start() -> None:
    """每次打开一个新会话时，初始化当前会话的消息记忆。"""
    cl.user_session.set("messages", [])
    await cl.Message(
        content=(
            "GAIA Agent 已启动。你可以直接输入问题；"
            "如果问题涉及文件，请把 task_id 和文件名一起告诉我。"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """处理用户每一次输入，并把它交给 LangGraph agent。"""
    history: list[AnyMessage] = cl.user_session.get("messages") or []
    history.append(HumanMessage(content=message.content))

    ui_message = cl.Message(content="正在调用 agent，请稍等...")
    await ui_message.send()

    try:
        # react_graph.invoke 是同步函数；用 make_async 避免阻塞 Chainlit 事件循环。
        result = await cl.make_async(react_graph.invoke)(
            {"messages": history},
            config={"recursion_limit": RECURSION_LIMIT},
        )
        new_history = result["messages"]
        cl.user_session.set("messages", new_history)

        ui_message.content = get_last_ai_answer(new_history)
    except Exception as error:
        # 失败时也保留用户问题，方便你继续追问或复盘。
        cl.user_session.set("messages", history)
        ui_message.content = f"Agent run failed: {error}"

    await ui_message.update()
