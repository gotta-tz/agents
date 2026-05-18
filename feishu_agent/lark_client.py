import requests
import time
import json

class LarkClient:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.token_expires_at = 0

    def get_access_token(self):
        """获取 tenant_access_token"""
        if time.time() < self.token_expires_at:
            return self.access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        })
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data}")

        self.access_token = data["tenant_access_token"]
        self.token_expires_at = time.time() + data.get("expire", 7200) - 300
        return self.access_token

    def send_text(self, receive_id, text, receive_id_type="open_id"):
        """发送文本消息

        Args:
            receive_id: 接收者 ID
            text: 消息文本
            receive_id_type: 接收者 ID 类型，支持 open_id、user_id、union_id、email、chat_id
        """
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

        resp = requests.post(url, params=params, headers=headers, json=payload)
        print(f"[发送消息] receive_id={receive_id}, status={resp.status_code}, body={resp.text[:500] if resp.text else 'empty'}")
        resp.raise_for_status()
        return resp.json()
