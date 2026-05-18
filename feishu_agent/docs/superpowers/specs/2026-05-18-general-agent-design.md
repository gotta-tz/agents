# 飞书综合智能体框架设计

## 概述

将现有的单一功能（5寸照片打印）扩展为可插拔的综合智能体框架，支持多 Skill、多 Bot 协作。

## 背景

**现状**：
- 单一 Bot，只能处理 5 寸照片打印
- 意图识别：硬编码关键词匹配
- 状态管理：全局字典，无持久化

**目标**：
- 框架优先，支持 Skill 插件化
- LLM 意图识别，支持自然语言
- 流式输出，逐段实时发送
- 未来支持多 Bot 协作

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      Main Bot                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ LLM Intent │→ │  Skill Host   │→ │   Lark SDK   │ │
│  │  Engine    │  │   (调度器)    │  │  (飞书 API)   │ │
│  └─────────────┘  └──────────────┘  └──────────────┘ │
│         │                 │                              │
│         ▼                 ▼                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │               Skill Registry                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐      │  │
│  │  │PhotoPrint│ │ General  │ │Calendar  │ ...   │  │
│  │  │  Skill   │ │  Chat    │ │  Skill   │      │  │
│  │  └──────────┘ └──────────┘ └──────────┘      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Phase 划分

**Phase 1: Bot as Skill Host（当前改造）**
- Skill 插件系统
- LLM Intent Engine
- 流式输出支持
- 迁移 PhotoPrint Skill

**Phase 2: 多 Skill 扩展**
- Calendar Skill
- Task Skill
- Doc Skill

**Phase 3: 多 Bot 协作**
- Bot Manager
- Bot 间通信

---

## 核心组件

### 1. Skill 接口

```python
# core/skill.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class SkillContext:
    """Skill 执行上下文"""
    user_id: str
    chat_id: str
    chat_type: str
    message_id: str
    content: Dict[str, Any]
    session_id: str = ""
    skill_data: Dict[str, Any] = {}

@dataclass
class SkillResult:
    """Skill 执行结果"""
    success: bool
    reply: str = ""
    data: Dict[str, Any] = {}
    consumed: bool = True
    stream: bool = False

class BaseSkill(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def description(self) -> str:
        return ""

    @property
    def examples(self) -> List[str]:
        return []

    @abstractmethod
    async def execute(self, ctx: SkillContext) -> SkillResult:
        pass
```

### 2. Skill Host（调度器）

```python
# core/skill_host.py
class SkillHost:
    def __init__(self, intent_engine, lark_service):
        self.intent_engine = intent_engine
        self.lark_service = lark_service
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        self._skills[skill.name] = skill

    async def process(self, event: Dict) -> SkillResult:
        ctx = self._parse_event(event)
        user_text = ctx.content.get("text", "")

        # 1. 意图识别
        skill_name, confidence = await self.intent_engine.route(
            user_text, list(self._skills.values())
        )

        # 2. 执行 Skill
        if skill_name != "unknown" and skill_name in self._skills:
            return await self._skills[skill_name].execute(ctx)

        # 3. 兜底：GeneralChat
        general_chat = self._skills.get("general_chat")
        if general_chat:
            return await general_chat.execute(ctx)

        return SkillResult(success=False, reply="无法理解你的请求")

    def _parse_event(self, event) -> SkillContext:
        # 解析飞书事件
        ...
```

### 3. LLM Intent Engine

```python
# core/intent/llm_engine.py
class LLMIntentEngine:
    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    async def route(self, user_message: str,
                    skills: List[BaseSkill]) -> Tuple[str, float]:
        """返回 (skill_name, confidence)"""
        skills_desc = "\n".join([
            f"- **{s.name}**: {s.description}"
            + (f"\n  示例: {', '.join(s.examples)}" if s.examples else "")
            for s in skills
        ])

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=f"""你是一个意图分类器。根据用户消息，识别最匹配的操作。
可用操作：
{skills_desc}
只返回操作名称，不添加解释。""",
            messages=[{"role": "user", "content": user_message}]
        )

        matched = response.content[0].text.strip().lower()

        for s in skills:
            if s.name.lower() in matched or matched in s.name.lower():
                return s.name, 0.8

        return "unknown", 0.0
```

### 4. 流式消息服务

```python
# services/lark_service.py
class LarkService:
    async def send_message_stream(self, receive_id, generator,
                                   receive_id_type="open_id"):
        """流式发送消息，逐段实时发送"""
        accumulated = ""
        async for chunk in generator:
            accumulated += chunk
            await self._send_text_async(receive_id, accumulated,
                                        receive_id_type)
        return accumulated

    async def _send_text_async(self, receive_id, text, receive_id_type):
        """异步发送文本"""
        ...
```

---

## Skill 设计

### PhotoPrint Skill

```python
# skills/photo_print/skill.py
class PhotoPrintSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "photo_print"

    @property
    def description(self) -> str:
        return "将图片排版成5寸照片Word文档并打印"

    @property
    def examples(self) -> List[str]:
        return ["5寸照片打印", "打印照片", "帮我打印图片"]

    async def execute(self, ctx: SkillContext) -> SkillResult:
        user_text = ctx.content.get("text", "")

        if any(kw in user_text for kw in ["5寸照片打印", "5寸打印"]):
            return await self._enter_collect_mode(ctx)

        if any(kw in user_text for kw in ["可以打印", "打印"]):
            return await self._execute_print(ctx)

        # ...
```

### GeneralChat Skill

```python
# skills/general_chat/skill.py
class GeneralChatSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "general_chat"

    @property
    def description(self) -> str:
        return "回答用户的一般性问题，进行日常对话"

    async def execute(self, ctx: SkillContext) -> SkillResult:
        user_text = ctx.content.get("text", "")

        async def generate():
            async with self.llm.messages.stream(
                model=self.model,
                system="你是一个友好的助手...",
                messages=[{"role": "user", "content": user_text}]
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        return SkillResult(success=True, stream=True,
                          data={"generator": generate})
```

---

## 目录结构

```
feishu_agent/
├── core/                      # 核心框架
│   ├── __init__.py
│   ├── skill.py              # Skill 基类
│   ├── skill_host.py         # 调度器
│   └── intent/
│       ├── __init__.py
│       └── llm_engine.py     # LLM 意图识别
├── skills/                    # Skill 插件
│   ├── __init__.py           # 自动注册
│   ├── photo_print/          # 照片打印
│   │   ├── __init__.py
│   │   ├── skill.py
│   │   ├── downloader.py     # 复用
│   │   ├── word_gen.py       # 复用
│   │   └── printer.py        # 复用
│   └── general_chat/         # 通用对话
│       ├── __init__.py
│       └── skill.py
├── services/                  # 公共服务
│   ├── __init__.py
│   └── lark_service.py
├── main.py                    # 启动入口
└── feishu_agent.py            # 保留，委托 core
```

---

## Phase 2 扩展：多 Bot 协作

```python
# core/bot_manager.py
class BotManager:
    """多 Bot 协调器"""

    def __init__(self):
        self._bots: Dict[str, SkillHost] = {}

    def create_bot(self, name: str) -> SkillHost:
        bot = SkillHost(LLMIntentEngine(), LarkService())
        self._bots[name] = bot
        return bot

    def get_bot(self, name: str) -> Optional[SkillHost]:
        return self._bots.get(name)

    def route_event(self, event: Dict) -> SkillResult:
        """根据事件路由到对应 Bot"""
        # 可根据 chat_id、user_id 路由
        # 或使用 LLM 判断
        ...
```

---

## 实施计划

| Phase | 内容 | 产出 |
|-------|------|------|
| 1 | 核心框架搭建 | `core/skill.py`, `skill_host.py`, `llm_engine.py` |
| 2 | PhotoPrint Skill 迁移 | `skills/photo_print/` |
| 3 | GeneralChat Skill | `skills/general_chat/` + 流式输出 |
| 4 | 服务化和入口 | `main.py`, `lark_service.py` |
| 5 | 向后兼容 | 保留 `feishu_agent.py` |

---

## 验证方法

1. HTTP 测试：
   ```bash
   curl http://127.0.0.1:8888/health  # → OK
   ```

2. Skill 测试：
   - 发送「5寸照片打印」→ PhotoPrint Skill 响应
   - 发送「你好」→ GeneralChat Skill 响应（流式）

3. 扩展测试：
   - 注册新 Skill
   - 验证 LLM 正确路由
