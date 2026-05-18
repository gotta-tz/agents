"""Skill Host - 核心调度器."""
import json
from typing import Dict, List, Optional
from core.skill import BaseSkill, SkillContext, SkillResult


class SkillHost:
    """Skill 宿主/调度器."""

    def __init__(self, intent_engine, lark_service):
        self.intent_engine = intent_engine
        self.lark_service = lark_service
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        """注册 Skill."""
        self._skills[skill.name] = skill
        print(f"[SkillHost] Registered: {skill.name}")

    def unregister(self, name: str):
        """注销 Skill."""
        if name in self._skills:
            del self._skills[name]
            print(f"[SkillHost] Unregistered: {name}")

    async def process(self, event: Dict) -> SkillResult:
        """处理消息."""
        ctx = self._parse_event(event)

        user_text = ctx.content.get("text", "")
        skill_name, confidence = await self.intent_engine.route(
            user_text, list(self._skills.values())
        )

        print(f"[SkillHost] Intent: {skill_name} (confidence: {confidence})")

        if skill_name != "unknown" and skill_name in self._skills:
            skill = self._skills[skill_name]
            return await skill.execute(ctx)

        general_chat = self._skills.get("general_chat")
        if general_chat:
            return await general_chat.execute(ctx)

        return SkillResult(
            success=False,
            reply="抱歉，我无法理解你的请求。"
        )

    def _parse_event(self, event: Dict) -> SkillContext:
        """解析飞书事件为 SkillContext."""
        message = event.get("event", {}).get("message", {})
        sender = event.get("event", {}).get("sender", {})
        msg_type = message.get("msg_type", "")
        content = message.get("content", "{}")

        try:
            parsed_content = json.loads(content)
        except:
            parsed_content = {"text": content}

        return SkillContext(
            user_id=sender.get("sender_id", {}).get("open_id", ""),
            chat_id=event.get("event", {}).get("chat_id", ""),
            chat_type=message.get("chat_type", "p2p"),
            message_id=message.get("message_id", ""),
            content=parsed_content
        )