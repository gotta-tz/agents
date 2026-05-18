"""基于 LLM 的意图识别引擎."""
import os
from typing import List, Tuple, Optional

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class LLMIntentEngine:
    """LLM 意图识别引擎."""

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "claude-opus-4-6"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.client = None
        if self.api_key and HAS_ANTHROPIC:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    async def route(self, user_message: str,
                    skills: List["BaseSkill"]) -> Tuple[str, float]:
        """将用户消息路由到最匹配的 Skill.

        Returns:
            (skill_name, confidence) 或 ("unknown", 0.0)
        """
        if not skills:
            return "unknown", 0.0

        if not self.client:
            return "unknown", 0.0

        skills_desc = "\n".join([
            f"- **{s.name}**: {s.description}"
            + (f"\n  示例: {', '.join(s.examples)}" if s.examples else "")
            for s in skills
        ])

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=f"""你是一个意图分类器。根据用户消息，识别用户想要执行的操作。
只能选择一个最匹配的操作返回。

可用操作：
{skills_desc}

返回格式：
- 如果匹配：只返回操作名称（小写）
- 如果不匹配：返回 "unknown"

不要添加任何解释，只返回操作名称。""",
            messages=[{"role": "user", "content": user_message}]
        )

        matched = response.content[0].text.strip().lower()

        skill_names = [s.name.lower() for s in skills]
        if matched in skill_names:
            return matched, 1.0

        for s in skills:
            if s.name.lower() in matched or matched in s.name.lower():
                return s.name, 0.8

        return "unknown", 0.0