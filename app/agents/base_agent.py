"""
BaseAgent — shared foundation for all Costco Tyre Agent agents.
Uses LangGraph's create_react_agent (LangChain 1.x recommended pattern).
Memory is handled via MemorySaver checkpointer keyed by session_id (thread_id).
"""
from __future__ import annotations
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()


def get_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        temperature=0,
        max_tokens=2048,
    )


class BaseAgent:
    """
    All agents extend BaseAgent. Subclasses set:
      - system_prompt: str
      - tools: list[BaseTool]
    """

    system_prompt: str = "You are a helpful Costco tyre assistant."
    tools: list[BaseTool] = []

    def __init__(self) -> None:
        self.llm = get_llm()
        self._checkpointer = MemorySaver()
        self._agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self.system_prompt,
            checkpointer=self._checkpointer,
        )

    def run(self, input: str, session_id: str) -> str:
        """
        Run the agent for a given input and session.
        session_id maps to LangGraph's thread_id for persistent memory (10-turn window).
        """
        config = {"configurable": {"thread_id": session_id}}
        result = self._agent.invoke(
            {"messages": [("user", input)]},
            config=config,
        )
        # Last message in the graph output is the assistant's reply
        messages = result.get("messages", [])
        if messages:
            return messages[-1].content
        return ""
