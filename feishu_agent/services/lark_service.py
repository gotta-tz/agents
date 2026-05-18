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