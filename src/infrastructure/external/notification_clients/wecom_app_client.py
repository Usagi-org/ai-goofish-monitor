"""
企业微信应用消息通知客户端
通过企微应用 API 推送消息到指定用户（非群机器人 Webhook）
"""
import asyncio
import html
import time
from typing import Dict

import requests

from .base import NotificationClient


class WeComAppClient(NotificationClient):
    """企业微信应用消息通知客户端"""

    channel_key = "wecom_app"
    display_name = "企微应用"

    def __init__(
        self,
        corpid: str | None = None,
        corpsecret: str | None = None,
        agentid: int | str | None = None,
        touser: str | None = None,
        pcurl_to_mobile: bool = True,
    ):
        enabled = bool(corpid and corpsecret and agentid)
        super().__init__(enabled=enabled, pcurl_to_mobile=pcurl_to_mobile)
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.agentid = agentid
        self.touser = touser or "@all"
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    def _get_access_token(self) -> str:
        """获取 access_token，带缓存（有效期内不重复请求）"""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {"corpid": self.corpid, "corpsecret": self.corpsecret}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(
                f"获取企微 access_token 失败: {data.get('errmsg', '未知错误')}"
            )
        self._access_token = data["access_token"]
        # 提前 5 分钟过期，避免边界问题
        self._token_expires_at = now + data.get("expires_in", 7200) - 300
        return self._access_token

    async def send(self, product_data: Dict, reason: str) -> bool:
        if not self.is_enabled():
            raise RuntimeError("企微应用 未启用")

        message = self._build_message(product_data, reason)

        # HTML-escape user-provided data before rendering the TextCard description.
        safe_title = html.escape(str(message.title))
        safe_price = html.escape(str(message.price))
        safe_reason = html.escape(str(message.reason))

        # 构建 text card 消息（支持点击卡片或按钮跳转）
        description_lines = [
            f"📦 商品: {safe_title}",
            f"💰 价格: {safe_price}",
            f"📝 原因: {safe_reason}",
            "📱 点击卡片或下方按钮查看详情",
        ]

        payload = {
            "touser": self.touser,
            "msgtype": "textcard",
            "agentid": int(self.agentid),
            "textcard": {
                "title": message.notification_title,
                "description": "\n".join(description_lines),
                "url": message.mobile_link or message.desktop_link,
                "btntxt": "查看详情",
            },
        }

        loop = asyncio.get_running_loop()
        token = await loop.run_in_executor(None, self._get_access_token)
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"

        response = await loop.run_in_executor(
            None,
            lambda: requests.post(url, json=payload, timeout=10),
        )
        response.raise_for_status()
        result = response.json()
        if result.get("errcode", 0) != 0:
            # token 过期时重试一次
            if result.get("errcode") in (40014, 42001):
                self._access_token = None
                self._token_expires_at = 0
                token = await loop.run_in_executor(None, self._get_access_token)
                url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(url, json=payload, timeout=10),
                )
                response.raise_for_status()
                result = response.json()
                if result.get("errcode", 0) != 0:
                    raise RuntimeError(
                        f"企微应用消息发送失败: {result.get('errmsg', '未知错误')}"
                    )
            else:
                raise RuntimeError(
                    f"企微应用消息发送失败: {result.get('errmsg', '未知错误')}"
                )
        return True
