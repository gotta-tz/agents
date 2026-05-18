import os
import requests
from pathlib import Path
import uuid

class ImageDownloader:
    def __init__(self, save_dir):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def download_from_feishu(self, file_key, lark_client, message_id=None):
        """
        从飞书下载图片
        file_key: 飞书消息中的 file_key
        message_id: 消息 ID（用于下载图片资源）
        返回本地文件路径
        """
        token = lark_client.get_access_token()

        # 优先使用 message_resource API 下载图片
        if message_id:
            url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
            params = {"type": "image"}
        else:
            # 旧 API（已废弃）
            url = f"https://open.feishu.cn/open-apis/im/v1/images/{file_key}"
            params = {}

        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()

        # 获取文件扩展名
        content_type = resp.headers.get("Content-Type", "")
        ext = self._get_ext(content_type)

        # 生成唯一文件名
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = self.save_dir / filename

        # 保存文件
        with open(filepath, "wb") as f:
            f.write(resp.content)

        return str(filepath)

    def _get_ext(self, content_type):
        """根据 content type 获取扩展名"""
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        return ext_map.get(content_type, ".jpg")
