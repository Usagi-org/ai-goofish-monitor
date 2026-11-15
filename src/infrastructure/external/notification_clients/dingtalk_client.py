"""
钉钉群自定义机器人通知客户端
"""
import asyncio
import base64
import hashlib
import hmac
import re
import time
from typing import Dict
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

import requests

from .base import NotificationClient


class DingTalkClient(NotificationClient):
    """钉钉群自定义机器人通知客户端"""

    channel_key = "dingtalk"
    display_name = "钉钉"

    def __init__(
        self,
        webhook_url: str | None = None,
        secret: str | None = None,
        pcurl_to_mobile: bool = True,
    ):
        super().__init__(enabled=bool(webhook_url), pcurl_to_mobile=pcurl_to_mobile)
        self.webhook_url = webhook_url
        self.secret = secret.strip() if isinstance(secret, str) and secret.strip() else None

    def _build_url(self) -> str:
        if not self.secret:
            return self.webhook_url or ""

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = quote_plus(base64.b64encode(hmac_code))

        parsed = urlparse(self.webhook_url or "")
        query_items = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in {"timestamp", "sign"}
        ]
        base_query = urlencode(query_items)
        signed_suffix = f"timestamp={timestamp}&sign={sign}"
        final_query = f"{base_query}&{signed_suffix}" if base_query else signed_suffix
        return urlunparse(parsed._replace(query=final_query))

    async def send(self, product_data: Dict, reason: str) -> None:
        if not self.is_enabled():
            raise RuntimeError("钉钉 未启用")

        message = self._build_message(product_data, reason)
        markdown_lines = [f"## {message.notification_title}", ""]
        if message.image_url:
            markdown_lines.append(f"![商品图片]({message.image_url})")
            markdown_lines.append("")
        markdown_lines.append(f"- 价格: {message.price}")
        markdown_lines.append(f"- 原因: {message.reason}")
        if message.mobile_link:
            markdown_lines.append(f"- 手机端链接: [{message.mobile_link}]({message.mobile_link})")
        markdown_lines.append(f"- 电脑端链接: [{message.desktop_link}]({message.desktop_link})")

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": message.notification_title,
                "text": "\n".join(markdown_lines),
            },
        }
        headers = {"Content-Type": "application/json"}
        target_url = self._build_url()

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    target_url,
                    json=payload,
                    headers=headers,
                    timeout=10,
                ),
            )
        except requests.Timeout:
            raise RuntimeError("钉钉请求超时") from None
        except requests.RequestException:
            raise RuntimeError("钉钉请求异常：网络连接失败") from None

        if not response.ok:
            raise RuntimeError(f"钉钉请求失败 (HTTP {response.status_code})")

        try:
            result = response.json()
        except ValueError:
            raise RuntimeError("钉钉返回了无法解析的响应") from None

        if (
            isinstance(result, dict)
            and "errcode" in result
            and type(result["errcode"]) is int
            and result["errcode"] == 0
        ):
            return

        detail = ""
        if isinstance(result, dict):
            for key in ("errmsg", "error", "message"):
                raw_value = result.get(key)
                if isinstance(raw_value, str) and raw_value.strip():
                    detail = self._sanitize_error_detail(raw_value, target_url)
                    if detail:
                        break

        if detail:
            raise RuntimeError(detail)

        if isinstance(result, dict) and "errcode" in result and type(result["errcode"]) is int:
            raise RuntimeError(f"钉钉返回未知错误 (errcode={result['errcode']})")

        raise RuntimeError("钉钉返回异常响应（缺少有效 errcode）")

    def _sanitize_error_detail(self, detail: str, target_url: str = "") -> str:
        sanitized = detail.strip()
        if not sanitized:
            return ""

        sensitive_literals: list[str] = []
        for candidate_url in (target_url, self.webhook_url or ""):
            if not candidate_url:
                continue
            sensitive_literals.append(candidate_url)
            parsed = urlparse(candidate_url)
            if parsed.query:
                sensitive_literals.append(parsed.query)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                if key.lower() in {"access_token", "sign"} and value:
                    sensitive_literals.append(value)
                    sensitive_literals.append(quote_plus(value))

        if self.secret:
            sensitive_literals.append(self.secret)
            sensitive_literals.append(quote_plus(self.secret))

        for literal in sorted(set(sensitive_literals), key=len, reverse=True):
            if literal:
                sanitized = sanitized.replace(literal, "[已脱敏]")

        sanitized = re.sub(
            r"(?i)\b(access_token|sign|secret|timestamp)\s*[=:]\s*[^\s&\"',;)\]]+",
            "[已脱敏]",
            sanitized,
        )
        sanitized = re.sub(r"(?i)access_token", "token", sanitized)
        sanitized = re.sub(r"(?i)sign\s*=", "[已脱敏]", sanitized)
        return sanitized[:200]
