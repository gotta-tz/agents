# 综合智能体框架实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建支持 Skill 插件系统、LLM 意图识别、流式输出的飞书智能体框架

**Architecture:** 采用 Skill Host 模式，Skill 注册到 Host，Host 根据 LLM 意图识别结果分发到对应 Skill 执行。流式消息通过异步迭代器实现逐段发送。

**Tech Stack:** Python 3.14, lark-oapi, anthropic, asyncio

---

## 文件结构

```
feishu_agent/
├── core/
│   ├── __init__.py
│   ├── skill.py              # Skill 基类、Context、Result
│   ├── skill_host.py          # Skill 调度器
│   └── intent/
│       ├── __init__.py
│       └── llm_engine.py     # LLM 意图识别
├── skills/
│   ├── __init__.py           # 自动注册入口
│   ├── photo_print/
│   │   ├── __init__.py
│   │   └── skill.py          # PhotoPrint Skill
│   └── general_chat/
│       ├── __init__.py
│       └── skill.py          # GeneralChat Skill
├── services/
│   ├── __init__.py
│   └── lark_service.py       # 飞书 API + 流式发送
├── main.py                   # 启动入口
└── feishu_agent.py           # 保留，委托 core
```

---

## Task 1: 创建核心 Skill 基础设施

**Files:**
- Create: `feishu_agent/core/__init__.py`
- Create: `feishu_agent/core/skill.py`

- [ ] **Step 1: 创建 core/__init__.py**

```python
"""Core framework for Feishu Agent."""
from core.skill import BaseSkill, SkillContext, SkillResult

__all__ = ["BaseSkill", "SkillContext", "SkillResult"]
```

- [ ] **Step 2: 创建 core/skill.py - Skill 基类**

```python
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
```

- [ ] **Step 3: 验证文件创建**

Run: `ls -la feishu_agent/core/`
Expected: `__init__.py` 和 `skill.py` 存在

- [ ] **Step 4: 提交**

```bash
git add feishu_agent/core/
git commit -m "feat(core): 添加 Skill 基类和核心数据结构"
```

---

## Task 2: 创建 LLM 意图识别引擎

**Files:**
- Create: `feishu_agent/core/intent/__init__.py`
- Create: `feishu_agent/core/intent/llm_engine.py`

- [ ] **Step 1: 创建 core/intent/__init__.py**

```python
"""Intent recognition engine."""
from core.intent.llm_engine import LLMIntentEngine

__all__ = ["LLMIntentEngine"]
```

- [ ] **Step 2: 创建 core/intent/llm_engine.py**

```python
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
            # 无 LLM 时降级为 unknown
            return "unknown", 0.0

        skills_desc = "\n".join([
            f"- **{s.name}**: {s.description}"
            + (f"\n  示例: {', '.join(s.examples)}" if s.examples else "")
            for s in skills
        ])

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system="""你是一个意图分类器。根据用户消息，识别用户想要执行的操作。
只能选择一个最匹配的操作返回。

可用操作：
{skills_desc}

返回格式：
- 如果匹配：只返回操作名称（小写）
- 如果不匹配：返回 "unknown"

不要添加任何解释，只返回操作名称。""".format(skills_desc=skills_desc),
            messages=[{"role": "user", "content": user_message}]
        )

        matched = response.content[0].text.strip().lower()

        # 验证匹配结果
        skill_names = [s.name.lower() for s in skills]
        if matched in skill_names:
            return matched, 1.0

        # 尝试模糊匹配
        for s in skills:
            if s.name.lower() in matched or matched in s.name.lower():
                return s.name, 0.8

        return "unknown", 0.0
```

- [ ] **Step 3: 验证文件创建**

Run: `ls -la feishu_agent/core/intent/`
Expected: `__init__.py` 和 `llm_engine.py` 存在

- [ ] **Step 4: 提交**

```bash
git add feishu_agent/core/intent/
git commit -m "feat(core): 添加 LLM 意图识别引擎"
```

---

## Task 3: 创建 Skill Host 调度器

**Files:**
- Create: `feishu_agent/core/skill_host.py`

- [ ] **Step 1: 创建 core/skill_host.py**

```python
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
        # 1. 解析消息
        ctx = self._parse_event(event)

        # 2. 意图识别
        user_text = ctx.content.get("text", "")
        skill_name, confidence = await self.intent_engine.route(
            user_text, list(self._skills.values())
        )

        print(f"[SkillHost] Intent: {skill_name} (confidence: {confidence})")

        # 3. 执行 Skill
        if skill_name != "unknown" and skill_name in self._skills:
            skill = self._skills[skill_name]
            return await skill.execute(ctx)

        # 4. 兜底：GeneralChat
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

        # 解析 content
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
```

- [ ] **Step 2: 更新 core/__init__.py**

```python
"""Core framework for Feishu Agent."""
from core.skill import BaseSkill, SkillContext, SkillResult
from core.skill_host import SkillHost
from core.intent.llm_engine import LLMIntentEngine

__all__ = ["BaseSkill", "SkillContext", "SkillResult", "SkillHost", "LLMIntentEngine"]
```

- [ ] **Step 3: 验证**

Run: `python -c "from core import SkillHost, LLMIntentEngine; print('OK')"`
Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add feishu_agent/core/skill_host.py feishu_agent/core/__init__.py
git commit -m "feat(core): 添加 Skill Host 调度器"
```

---

## Task 4: 创建 LarkService（支持流式）

**Files:**
- Create: `feishu_agent/services/__init__.py`
- Create: `feishu_agent/services/lark_service.py`

- [ ] **Step 1: 创建 services/__init__.py**

```python
"""Services for Feishu Agent."""
from services.lark_service import LarkService

__all__ = ["LarkService"]
```

- [ ] **Step 2: 创建 services/lark_service.py**

```python
"""飞书 API 服务，支持流式消息."""
import json
import time
from typing import AsyncGenerator, Optional
import requests

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class LarkService:
    """飞书 API 封装."""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.token_expires_at = 0
        self.llm_client = None

        # 初始化 LLM 客户端
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and HAS_ANTHROPIC:
            self.llm_client = anthropic.Anthropic(api_key=api_key)

    def get_access_token(self) -> str:
        """获取 tenant_access_token."""
        if time.time() < self.token_expires_at:
            return self.access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data}")

        self.access_token = data["tenant_access_token"]
        self.token_expires_at = time.time() + data.get("expire", 7200) - 300
        return self.access_token

    async def send_text(self, receive_id: str, text: str,
                        receive_id_type: str = "open_id") -> dict:
        """发送文本消息."""
        token = self.get_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": receive_id_type}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }

        resp = requests.post(url, params=params, headers=headers,
                             json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    async def send_message_stream(self, receive_id: str,
                                  generator: AsyncGenerator[str, None],
                                  receive_id_type: str = "open_id") -> str:
        """流式发送消息，逐段实时发送."""
        accumulated = ""
        async for chunk in generator:
            accumulated += chunk
            # 发送已生成的部分
            try:
                await self.send_text(receive_id, accumulated, receive_id_type)
            except Exception as e:
                print(f"[LarkService] Stream send error: {e}")
        return accumulated

    async def send_image(self, receive_id: str, image_key: str,
                        receive_id_type: str = "open_id") -> dict:
        """发送图片消息."""
        token = self.get_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": receive_id_type}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": "image",
            "content": json.dumps({"image_key": image_key})
        }

        resp = requests.post(url, params=params, headers=headers,
                             json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 3: 验证**

Run: `python -c "from services import LarkService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: 提交**

```bash
git add feishu_agent/services/
git commit -m "feat(services): 添加 LarkService，支持流式消息发送"
```

---

## Task 5: 创建 PhotoPrint Skill

**Files:**
- Create: `feishu_agent/skills/photo_print/__init__.py`
- Create: `feishu_agent/skills/photo_print/skill.py`
- Modify: `feishu_agent/config.py` (添加 ANTHROPIC_API_KEY)

- [ ] **Step 1: 创建 skills/photo_print/__init__.py**

```python
"""Photo Print Skill."""
from skills.photo_print.skill import PhotoPrintSkill

__all__ = ["PhotoPrintSkill"]
```

- [ ] **Step 2: 创建 skills/photo_print/skill.py**

```python
"""5寸照片打印 Skill."""
import time
import shutil
from pathlib import Path
from typing import List
from core.skill import BaseSkill, SkillContext, SkillResult

# 复用现有的模块
import sys
from pathlib import Path as P
sys.path.insert(0, str(P(__file__).parent.parent.parent))

from image_downloader import ImageDownloader
from word_generator import WordGenerator
from printer import Printer


class PhotoPrintSkill(BaseSkill):
    """5寸照片打印 Skill."""

    def __init__(self, config, lark_service):
        self.image_input_dir = config.IMAGE_INPUT_DIR
        self.word_output_dir = config.WORD_OUTPUT_DIR
        self.word_script_path = config.WORD_SCRIPT_PATH
        self.python_path = config.PYTHON_PATH
        self.timeout = config.TIMEOUT_SECONDS
        self.printer_name = config.PRINTER_NAME
        self.lark = lark_service

        self.downloader = ImageDownloader(self.image_input_dir)
        self.word_gen = WordGenerator(
            self.word_script_path, self.word_output_dir,
            self.python_path, self.timeout
        )
        self.printer = Printer(self.printer_name)

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
        user_text = ctx.content.get("text", "").lower()

        # 进入收集模式
        if any(kw in user_text for kw in ["5寸照片打印", "5寸打印"]):
            return await self._enter_collect_mode(ctx)

        # 确认打印
        if any(kw in user_text for kw in ["可以打印", "打印"]):
            return await self._execute_print(ctx)

        # 取消
        if any(kw in user_text for kw in ["取消", "退出打印"]):
            return await self._cancel(ctx)

        # 帮助
        if "帮助" in user_text or "help" in user_text:
            return SkillResult(
                success=True,
                reply="📷 请先说「5寸照片打印」开始收集模式，然后发送图片，最后说「可以打印」。"
            )

        # 其他：显示当前状态
        images = ctx.skill_data.get("images", [])
        return SkillResult(
            success=True,
            reply=f"📷 已收录 {len(images)} 张图片。说「可以打印」生成 Word，「取消」放弃。"
        )

    async def _enter_collect_mode(self, ctx: SkillContext) -> SkillResult:
        """进入收集模式."""
        batch_folder = Path(self.image_input_dir) / f"batch_{int(time.time())}"
        batch_folder.mkdir(parents=True, exist_ok=True)

        ctx.skill_data["folder"] = str(batch_folder)
        ctx.skill_data["images"] = []

        return SkillResult(
            success=True,
            reply="📷 进入5寸照片打印模式，请发送图片。发送完成后说「可以打印」。",
            data={"folder": str(batch_folder)}
        )

    async def _execute_print(self, ctx: SkillContext) -> SkillResult:
        """执行打印."""
        images = ctx.skill_data.get("images", [])
        folder = ctx.skill_data.get("folder")

        if not images:
            return SkillResult(success=False, reply="没有待处理的图片")

        # 生成 Word
        word_result = self.word_gen.generate(folder)
        if not word_result["success"]:
            return SkillResult(success=False,
                             reply=f"生成Word失败: {word_result.get('error')}")

        word_path = word_result["output_path"]

        # 打印
        print_result = self.printer.print_file(word_path)
        if not print_result["success"]:
            return SkillResult(success=False,
                             reply=f"打印失败: {print_result.get('error')}")

        # 清理
        shutil.rmtree(folder, ignore_errors=True)

        return SkillResult(
            success=True,
            reply=f"✅ 打印任务已完成！\n"
                  f"图片数量: {len(images)} 张\n"
                  f"打印机: {print_result.get('printer')}"
        )

    async def _cancel(self, ctx: SkillContext) -> SkillResult:
        """取消打印."""
        folder = ctx.skill_data.get("folder")
        if folder:
            shutil.rmtree(folder, ignore_errors=True)

        ctx.skill_data.clear()
        return SkillResult(success=True, reply="❌ 已取消，图片已清除。")
```

- [ ] **Step 3: 更新 config.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 飞书配置
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")

# LLM API 配置
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

# ... 其他保持不变
```

- [ ] **Step 4: 提交**

```bash
git add feishu_agent/skills/photo_print/ feishu_agent/config.py
git commit -m "feat(skills): 添加 PhotoPrint Skill"
```

---

## Task 6: 创建 GeneralChat Skill（流式）

**Files:**
- Create: `feishu_agent/skills/general_chat/__init__.py`
- Create: `feishu_agent/skills/general_chat/skill.py`

- [ ] **Step 1: 创建 skills/general_chat/__init__.py**

```python
"""General Chat Skill."""
from skills.general_chat.skill import GeneralChatSkill

__all__ = ["GeneralChatSkill"]
```

- [ ] **Step 2: 创建 skills/general_chat/skill.py**

```python
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

        # 构建流式生成器
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
```

- [ ] **Step 3: 提交**

```bash
git add feishu_agent/skills/general_chat/
git commit -m "feat(skills): 添加 GeneralChat Skill，支持流式输出"
```

---

## Task 7: 创建 skills/__init__.py 自动注册

**Files:**
- Create: `feishu_agent/skills/__init__.py`

- [ ] **Step 1: 创建 skills/__init__.py**

```python
"""Skills package - 自动注册入口."""
from typing import List

# Skill 注册表
_registered_skills = []


def register_skills(host, config, lark_service) -> List[str]:
    """注册所有 Skill 到 Host.

    Args:
        host: SkillHost 实例
        config: 配置对象
        lark_service: LarkService 实例

    Returns:
        已注册的 Skill 名称列表
    """
    from skills.photo_print import PhotoPrintSkill
    from skills.general_chat import GeneralChatSkill

    # 注册 PhotoPrint Skill
    photo_skill = PhotoPrintSkill(config, lark_service)
    host.register(photo_skill)
    _registered_skills.append("photo_print")

    # 注册 GeneralChat Skill
    chat_skill = GeneralChatSkill(lark_service)
    host.register(chat_skill)
    _registered_skills.append("general_chat")

    return _registered_skills


__all__ = ["register_skills"]
```

- [ ] **Step 2: 提交**

```bash
git add feishu_agent/skills/__init__.py
git commit -m "feat(skills): 添加 Skill 自动注册入口"
```

---

## Task 8: 创建 main.py 启动入口

**Files:**
- Create: `feishu_agent/main.py`

- [ ] **Step 1: 创建 main.py**

```python
"""飞书智能体启动入口."""
import os
import sys
import threading
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import lark_oapi as lark_sdk
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from core import SkillHost, LLMIntentEngine
from services import LarkService
from skills import register_skills
from config import LARK_APP_ID, LARK_APP_SECRET


def create_agent():
    """创建 Agent 实例."""
    # 初始化服务
    lark_service = LarkService(LARK_APP_ID, LARK_APP_SECRET)

    # 初始化意图引擎
    intent_engine = LLMIntentEngine()

    # 初始化 Skill Host
    host = SkillHost(intent_engine, lark_service)

    # 注册 Skill
    register_skills(host, sys.modules[__name__], lark_service)

    return host, lark_service


def start_websocket_client(host, lark_service):
    """启动飞书 WebSocket 长连接."""

    async def handle_message_event(data: P2ImMessageReceiveV1) -> None:
        """SDK 消息处理函数."""
        try:
            event = {
                "event": {
                    "message": {
                        "msg_type": data.event.message.message_type,
                        "content": data.event.message.content,
                        "message_id": data.event.message.message_id,
                        "chat_type": data.event.message.chat_type
                    },
                    "sender": {
                        "sender_id": {
                            "open_id": data.event.sender.sender_id.open_id,
                            "sender_type": data.event.sender.sender_type
                        }
                    },
                    "chat_id": data.event.message.chat_id
                }
            }

            # 处理消息
            result = await host.process(event)

            # 发送回复
            if result.success:
                if result.stream:
                    # 流式输出
                    receive_id = event["event"]["sender"]["sender_id"]["open_id"]
                    await lark_service.send_message_stream(
                        receive_id,
                        result.data["generator"]
                    )
                else:
                    # 普通输出
                    receive_id = event["event"]["sender"]["sender_id"]["open_id"]
                    await lark_service.send_text(receive_id, result.reply)

        except Exception as e:
            print(f"[错误] {e}")
            import traceback
            traceback.print_exc()

    # 创建事件处理器
    event_handler = (
        lark_sdk.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(handle_message_event)
        .build()
    )

    # 创建 WebSocket 客户端
    cli = lark_sdk.ws.Client(
        LARK_APP_ID,
        LARK_APP_SECRET,
        event_handler=event_handler,
        log_level=lark_sdk.LogLevel.DEBUG
    )

    print("[飞书] 启动 WebSocket 长连接...")
    cli.start()


def main():
    """主入口."""
    print("[启动] 初始化飞书智能体...")

    # 创建 Agent
    host, lark_service = create_agent()
    print(f"[启动] 已注册 Skill: {list(host._skills.keys())}")

    # 启动 WebSocket
    ws_thread = threading.Thread(
        target=start_websocket_client,
        args=(host, lark_service),
        daemon=True
    )
    ws_thread.start()

    print("[启动] Agent 运行中，按 Ctrl+C 退出")
    ws_thread.join()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交**

```bash
git add feishu_agent/main.py
git commit -m "feat: 添加 main.py 启动入口"
```

---

## Task 9: 保留 feishu_agent.py 向后兼容

**Files:**
- Modify: `feishu_agent/feishu_agent.py`

- [ ] **Step 1: 更新 feishu_agent.py 委托给 core**

```python
"""飞书智能体 - 向后兼容入口.

此文件保留用于兼容，核心逻辑已迁移到 core/ 和 main.py
"""
import main as _main

if __name__ == "__main__":
    _main.main()
```

- [ ] **Step 2: 提交**

```bash
git add feishu_agent/feishu_agent.py
git commit -m "refactor: feishu_agent.py 委托给 core"
```

---

## Task 10: 验证测试

**Files:**
- Test: `feishu_agent/core/skill.py`
- Test: `feishu_agent/core/skill_host.py`

- [ ] **Step 1: 测试 Skill 基类**

Run: `python -c "
from core import BaseSkill, SkillContext, SkillResult

class TestSkill(BaseSkill):
    @property
    def name(self):
        return 'test'
    async def execute(self, ctx):
        return SkillResult(success=True, reply='OK')

import asyncio
async def test():
    ctx = SkillContext(
        user_id='u1',
        chat_id='c1',
        chat_type='p2p',
        message_id='m1',
        content={'text': 'hello'}
    )
    result = await TestSkill().execute(ctx)
    assert result.success
    assert result.reply == 'OK'
    print('Skill test PASSED')

asyncio.run(test())
"`
Expected: `Skill test PASSED`

- [ ] **Step 2: 测试 SkillHost**

Run: `python -c "
from core import SkillHost, BaseSkill, SkillContext, SkillResult
from unittest.mock import MagicMock

class TestSkill(BaseSkill):
    @property
    def name(self):
        return 'test'
    async def execute(self, ctx):
        return SkillResult(success=True, reply='test ok')

async def test():
    mock_intent = MagicMock()
    mock_intent.route.return_value = ('test', 1.0)
    mock_lark = MagicMock()

    host = SkillHost(mock_intent, mock_lark)
    host.register(TestSkill())

    event = {
        'event': {
            'message': {
                'msg_type': 'text',
                'content': '{\"text\": \"test\"}',
                'chat_type': 'p2p',
                'message_id': 'm1'
            },
            'sender': {
                'sender_id': {
                    'open_id': 'u1',
                    'sender_type': 'user'
                }
            },
            'chat_id': 'c1'
        }
    }

    result = await host.process(event)
    assert result.success
    assert result.reply == 'test ok'
    print('SkillHost test PASSED')

asyncio.run(test())
"`
Expected: `SkillHost test PASSED`

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "test: 添加 Skill 和 SkillHost 单元测试"
```

---

## 实施完成

所有 Task 已完成。验证服务运行：

```bash
cd /Users/gotta/agents/feishu_agent
python main.py
```
