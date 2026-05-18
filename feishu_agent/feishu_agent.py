import json
import threading
import os
from flask import Flask
from pathlib import Path

import lark_oapi as lark_sdk
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from config import (
    LARK_APP_ID, LARK_APP_SECRET,
    BASE_DIR, IMAGE_INPUT_DIR, WORD_OUTPUT_DIR, WORD_SCRIPT_PATH,
    PYTHON_PATH, PRINTER_NAME, TIMEOUT_SECONDS
)
from lark_client import LarkClient
from image_downloader import ImageDownloader
from word_generator import WordGenerator
from printer import Printer

app = Flask(__name__)

# 初始化组件
lark = LarkClient(LARK_APP_ID, LARK_APP_SECRET)  # 飞书 API 客户端
downloader = ImageDownloader(IMAGE_INPUT_DIR)
word_gen = WordGenerator(WORD_SCRIPT_PATH, WORD_OUTPUT_DIR, PYTHON_PATH, TIMEOUT_SECONDS)
printer = Printer(PRINTER_NAME)

# 批次管理：{chat_id: {"images": [], "timer": None, "folder": Path}}
pending_batches = {}
BATCH_DELAY = 3  # 秒，等待更多图片的时间


def clear_image_folder(folder_path):
    """
    清空图片文件夹中的所有图片，并删除文件夹
    Returns: 被删除的文件数量
    """
    folder = Path(folder_path)
    if not folder.exists():
        return 0

    cleared = 0
    for file in folder.glob("*"):
        if file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            try:
                file.unlink()
                cleared += 1
                print(f"[清理] 删除图片: {file.name}")
            except Exception as e:
                print(f"[清理失败] {file.name}: {e}")

    # 删除文件夹本身
    try:
        folder.rmdir()
        print(f"[清理] 删除文件夹: {folder.name}")
    except Exception as e:
        print(f"[删除文件夹失败] {folder}: {e}")

    return cleared


def process_images(image_paths):
    """
    处理流程：
    1. 生成 Word（所有图片汇总到一份Word）
    2. 打印
    3. 清空图片文件夹
    4. 返回结果
    """
    if not image_paths:
        return [{"success": False, "error": "没有图片"}]

    # 所有图片放在同一个目录
    image_dir = str(Path(image_paths[0]).parent)

    # 1. 生成 Word（一次性处理目录下所有图片）
    print(f"[处理] 图片目录: {image_dir}, 图片数量: {len(image_paths)}")
    word_result = word_gen.generate(image_dir)

    if not word_result["success"]:
        return [{
            "image": image_paths[0],
            "success": False,
            "error": word_result.get("error", "生成失败")
        }]

    word_path = word_result["output_path"]
    print(f"[成功] Word 生成: {word_path}")

    # 2. 打印
    print_result = printer.print_file(word_path)

    if print_result["success"]:
        # 3. 打印成功后清空图片文件夹
        cleared_count = clear_image_folder(image_dir)

        return [{
            "success": True,
            "word_path": word_path,
            "job_id": print_result.get("job_id"),
            "printer": print_result.get("printer"),
            "cleared_files": cleared_count,
            "image_count": len(image_paths)
        }]
    else:
        return [{
            "success": False,
            "word_path": word_path,
            "error": print_result.get("error", "打印失败")
        }]


def handle_batch(chat_id, user_id):
    """处理一个批次的图片"""
    batch = pending_batches.get(chat_id)
    if not batch or not batch["images"]:
        return

    # 取消之前的定时器
    if batch["timer"]:
        batch["timer"].cancel()

    images = batch["images"]
    folder = batch["folder"]

    print(f"[批次处理] chat={chat_id}, 图片数={len(images)}")

    # 处理图片
    process_results = process_images(images)

    # 发送通知
    for result in process_results:
        reply_target = batch.get("reply_target", user_id)
        reply_id_type = batch.get("reply_id_type", "open_id")
        if result["success"]:
            printer_name = result.get("printer", "默认打印机")
            image_count = result.get("image_count", len(images))
            cleared = result.get("cleared_files", 0)
            lark.send_text(
                reply_target,
                f"✅ 打印任务已完成！\n\n"
                f"图片数量: {image_count} 张\n"
                f"打印机: {printer_name}\n"
                f"已清理图片: {cleared} 张",
                receive_id_type=reply_id_type
            )
        else:
            lark.send_text(
                reply_target,
                f"❌ 处理失败: {result.get('error', '未知错误')}",
                receive_id_type=reply_id_type
            )

    # 清理批次数据
    del pending_batches[chat_id]


def handle_message(event):
    """处理接收到的消息"""
    try:
        message = event.get("event", {})
        msg_type = message.get("message", {}).get("msg_type", "")
        content = json.loads(message.get("message", {}).get("content", "{}"))
        message_id = message.get("message", {}).get("message_id", "")

        sender = message.get("sender", {})
        user_id = sender.get("sender_id", {}).get("open_id", "unknown")
        chat_id = message.get("chat_id", "")
        chat_type = message.get("message", {}).get("chat_type", "p2p")

        # 确定回复目标：群聊回复到群，私聊回复到个人
        reply_target = chat_id if chat_type == "group" else user_id
        reply_id_type = "chat_id" if chat_type == "group" else "open_id"

        print(f"[收到消息] user={user_id}, chat_type={chat_type}, msg_type={msg_type}")

        # 跳过机器人自己的消息
        if sender.get("sender_id", {}).get("sender_type") == "app":
            return

        # 处理图片消息：只有进入收集模式后才收集
        if msg_type == "image":
            # 检查是否在收集模式
            if chat_id not in pending_batches:
                return  # 忽略，不发送任何消息

            file_key = content.get("image_key")
            if not file_key:
                return

            # 跳过重复的 file_key（飞书可能重复推送）
            batch = pending_batches[chat_id]
            if file_key in batch.get("seen_file_keys", set()):
                print(f"[跳过重复] file_key={file_key}")
                return

            # 下载图片到批次文件夹
            local_path = downloader.download_from_feishu(file_key, lark, message_id)
            print(f"[下载图片] {local_path}")

            # 添加到批次
            import shutil
            batch_img_path = batch["folder"] / Path(local_path).name
            shutil.move(local_path, batch_img_path)
            batch["images"].append(str(batch_img_path))
            batch.setdefault("seen_file_keys", set()).add(file_key)

            lark.send_text(reply_target, f"📷 第 {len(batch['images'])} 张图片已收录。说「可以打印」生成 Word。", receive_id_type=reply_id_type)

        # 处理文本消息
        elif msg_type == "text":
            user_text = content.get("text", "").strip().lower()

            # 用户说"5寸照片打印"时，进入收集模式
            if any(keyword in user_text for keyword in ["5寸照片打印", "5寸打印"]):
                import time
                batch_folder = Path(IMAGE_INPUT_DIR) / f"batch_{int(time.time())}"
                batch_folder.mkdir(parents=True, exist_ok=True)

                pending_batches[chat_id] = {
                    "images": [],
                    "timer": None,
                    "folder": batch_folder,
                    "user_id": user_id,
                    "reply_target": reply_target,
                    "reply_id_type": reply_id_type
                }
                lark.send_text(reply_target, "📷 进入5寸照片打印模式，请发送图片。发送完成后说「可以打印」。", receive_id_type=reply_id_type)

            # 用户说"可以打印"时，生成 Word
            elif any(keyword in user_text for keyword in ["可以打印", "打印"]):
                if chat_id in pending_batches and pending_batches[chat_id]["images"]:
                    handle_batch(chat_id, user_id)
                else:
                    lark.send_text(reply_target, "没有待处理的图片，请先说「5寸照片打印」开始收集。", receive_id_type=reply_id_type)
            elif any(keyword in user_text for keyword in ["帮助", "help"]):
                lark.send_text(reply_target, "📷 请先说「5寸照片打印」开始收集模式，然后发送图片，最后说「可以打印」。", receive_id_type=reply_id_type)
            elif any(keyword in user_text for keyword in ["取消", "退出打印"]):
                if chat_id in pending_batches:
                    batch = pending_batches[chat_id]
                    if batch["timer"]:
                        batch["timer"].cancel()
                    import shutil
                    shutil.rmtree(batch["folder"], ignore_errors=True)
                    del pending_batches[chat_id]
                    lark.send_text(reply_target, "❌ 已取消，当前图片已清除。", receive_id_type=reply_id_type)
                else:
                    lark.send_text(reply_target, "没有正在等待的图片。", receive_id_type=reply_id_type)
            else:
                if chat_id in pending_batches:
                    lark.send_text(reply_target, f"📷 已收录 {len(pending_batches[chat_id]['images'])} 张图片。说「可以打印」生成 Word，「取消」放弃。", receive_id_type=reply_id_type)
                else:
                    lark.send_text(reply_target, "📷 请先说「5寸照片打印」开始收集模式。", receive_id_type=reply_id_type)

    except Exception as e:
        print(f"[错误] {e}")
        import traceback
        traceback.print_exc()


def start_websocket_client():
    """使用飞书官方 SDK 启动 WebSocket 客户端接收飞书事件"""

    def handle_message_event(data: P2ImMessageReceiveV1) -> None:
        """SDK 消息处理函数"""
        try:
            # 转换为兼容格式
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
            handle_message(event)
        except Exception as e:
            print(f"[错误] {e}")
            import traceback
            traceback.print_exc()

    # 创建事件分发处理器
    # 注意：builder 的两个参数必须填空字符串
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
    # 启动客户端（会阻塞）
    cli.start()


@app.route("/health")
def health():
    return "OK"


@app.route("/printers")
def list_printers():
    """列出可用打印机"""
    printers = printer.list_printers()
    default = printer.get_default_printer()
    return {
        "printers": printers,
        "default": default
    }


@app.route("/test")
def test():
    """测试接口"""
    # 创建测试目录
    Path(IMAGE_INPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(WORD_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    return {
        "status": "ok",
        "base_dir": BASE_DIR,
        "image_dir": IMAGE_INPUT_DIR,
        "word_dir": WORD_OUTPUT_DIR,
        "script": WORD_SCRIPT_PATH
    }


if __name__ == "__main__":
    # 确保目录存在
    Path(IMAGE_INPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(WORD_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # 启动 WebSocket 客户端
    ws_thread = threading.Thread(target=start_websocket_client, daemon=True)
    ws_thread.start()

    # 启动 Flask 服务
    print(f"[启动] Agent 服务运行在 http://0.0.0.0:5000")
    print(f"[配置] 基础目录: {BASE_DIR}")
    print(f"[配置] 图片目录: {IMAGE_INPUT_DIR}")
    print(f"[配置] Word 输出: {WORD_OUTPUT_DIR}")
    print(f"[配置] 脚本路径: {WORD_SCRIPT_PATH}")
    print(f"[配置] 打印机: {PRINTER_NAME or '默认打印机'}")

    app.run(host="127.0.0.1", port=8888, debug=False)
