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
