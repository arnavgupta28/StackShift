"""StackShift agent. Role is injected at build time by agents/build.py."""

import os
from collections.abc import AsyncIterator

from agents import Agent, Runner
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from role import INSTRUCTIONS, TITLE, TOOL_NAMES
from tools import REGISTRY

MAX_TURNS = int(os.getenv("MAX_TURNS", "18"))


class StackShiftAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        self._model_name = os.getenv("OPENAI_MODEL") or os.getenv("MODEL", "gpt-4o-mini")
        model = OpenAIChatCompletionsModel(
            model=self._model_name,
            openai_client=self._client,
        )
        # Only this role's tools are bound. A tool that is not in this list
        # cannot be called by the model at all — that is the authority boundary.
        self._agent = Agent(
            name=TITLE,
            instructions=INSTRUCTIONS,
            tools=[REGISTRY[name] for name in TOOL_NAMES],
            model=model,
        )

    async def invoke(self, query: str, context_id: str) -> str:
        result = await Runner.run(self._agent, query, max_turns=MAX_TURNS)
        return result.final_output

    async def invoke_streaming(self, query: str, context_id: str) -> AsyncIterator[str]:
        result = await Runner.run(self._agent, query, max_turns=MAX_TURNS)
        yield result.final_output
