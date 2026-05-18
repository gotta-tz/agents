"""通用对话 Skill，支持流式输出."""
import os
from typing import List, AsyncGenerator
from core.skill import BaseSkill, SkillContext, SkillResult

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class GeneralChatSkill(BaseSkill):
    """通用对话 Skill."""

    def __init__(self, lark_service, model: str = "claude-opus-4-6"):
        self.lark = lark_service
        self.model = model
        self.llm_client = None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and HAS_ANTHROPIC:
            self.llm_client = anthropic.Anthropic(api_key=api_key)

    @property
    def name(self) -> str:
        return "general_chat"

    @property
    def description(self) -> str:
        return "回答用户的一般性问题，进行日常对话"

    async def execute(self, ctx: SkillContext) -> SkillResult:
        user_text = ctx.content.get("text", "")

        if not self.llm_client:
            return SkillResult(
                success=False,
                reply="抱歉，LLM 服务未配置。"
            )

        async def generate() -> AsyncGenerator[str, None]:
            async with self.llm_client.messages.stream(
                model=self.model,
                system="你是一个友好的飞书助手，帮助用户解答问题和日常对话。",
                messages=[{"role": "user", "content": user_text}]
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        return SkillResult(
            success=True,
            stream=True,
            data={"generator": generate}
        )