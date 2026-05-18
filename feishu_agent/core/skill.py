"""Skill 基类和核心数据结构."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class SkillContext:
    """Skill 执行上下文."""
    user_id: str
    chat_id: str
    chat_type: str  # "p2p" | "group"
    message_id: str
    content: Dict[str, Any]  # 消息内容
    session_id: str = ""
    skill_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Skill 执行结果."""
    success: bool
    reply: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    consumed: bool = True
    stream: bool = False


class BaseSkill(ABC):
    """Skill 基类."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill 唯一名称."""
        pass

    @property
    def description(self) -> str:
        """Skill 功能描述（供 LLM 理解）."""
        return ""

    @property
    def examples(self) -> List[str]:
        """示例用户指令."""
        return []

    @abstractmethod
    async def execute(self, ctx: SkillContext) -> SkillResult:
        """执行 Skill 逻辑."""
        pass