"""
通用 Webhook 通知客户端
"""
import asyncio
import json
from typing import Any, Dict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from .base import NotificationClient, NotificationMessage


class WebhookClient(NotificationClient):
    """通用 Webhook 通知客户端"""

    channel_key = "webhook"
    display_name = "Webhook"

    def __init__(
        self,
        webhook_url: str | None = None,
        webhook_method: str = "POST",
        webhook_headers: str | None = None,
        webhook_content_type: str = "JSON",
        webhook_query_parameters: str | None = None,
        webhook_body: str | None = None,
        pcurl_to_mobile: bool = True,
    ):
        super().__init__(enabled=bool(webhook_url), pcurl_to_mobile=pcurl_to_mobile)
        self.webhook_url = webhook_url
        self.webhook_method = (webhook_method or "POST").upper()
        self.webhook_headers = webhook_headers
        self.webhook_content_type = (webhook_content_type or "JSON").upper()
        self.webhook_query_parameters = webhook_query_parameters
        self.webhook_body = webhook_body

    async def send(self, product_data: Dict, reason: str) -> None:
        if not self.is_enabled():
            raise RuntimeError("Webhook 未启用")

        message = self._build_message(product_data, reason)
        headers = self._parse_json(self.webhook_headers, "WEBHOOK_HEADERS", expect_dict=True) or {}
        final_url = self._build_url(message)
        loop = asyncio.get_running_loop()

        if self.webhook_method == "GET":
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(final_url, headers=headers, timeout=15),
            )
            response.raise_for_status()
            return

        json_payload, form_payload = self._build_body(message, headers)
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                final_url,
                headers=headers,
                json=json_payload,
                data=form_payload,
                timeout=15,
            ),
        )
        response.raise_for_status()

    def _build_url(self, message: NotificationMessage) -> str:
        params = self._parse_json(
            self.webhook_query_parameters,
            "WEBHOOK_QUERY_PARAMETERS",
            expect_dict=True,
        ) or {}
        rendered = self._render_template(params, message)
        parsed_url = list(urlparse(self.webhook_url))
        query = dict(parse_qsl(parsed_url[4]))
        query.update(rendered)
        parsed_url[4] = urlencode(query)
        return urlunparse(parsed_url)

    def _build_body(
        self,
        message: NotificationMessage,
        headers: Dict[str, str],
    ) -> tuple[Any | None, Any | None]:
        if not self.webhook_body:
            return None, None

        body_template = self._parse_json(self.webhook_body, "WEBHOOK_BODY")
        rendered_body = self._render_template(body_template, message)

        if self.webhook_content_type == "JSON":
            if "Content-Type" not in headers and "content-type" not in headers:
                headers["Content-Type"] = "application/json; charset=utf-8"
            return rendered_body, None

        if self.webhook_content_type == "FORM":
            if not isinstance(rendered_body, dict):
                raise ValueError("WEBHOOK_BODY 在 FORM 模式下必须是 JSON 对象")
            if "Content-Type" not in headers and "content-type" not in headers:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            return None, rendered_body

        raise ValueError(f"不支持的 WEBHOOK_CONTENT_TYPE: {self.webhook_content_type}")

    def _parse_json(
        self,
        raw_value: str | None,
        field_name: str,
        expect_dict: bool = False,
    ) -> Any | None:
        if not raw_value:
            return None
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} 不是合法 JSON: {exc.msg}") from exc
        if expect_dict and not isinstance(parsed, dict):
            raise ValueError(f"{field_name} 必须是 JSON 对象")
        return parsed

    def _render_template(self, value: Any, message: NotificationMessage) -> Any:
        if isinstance(value, str):
            return self._replace_placeholders(value, message)
        if isinstance(value, list):
            return [self._render_template(item, message) for item in value]
        if isinstance(value, dict):
            return {
                key: self._render_template(item, message)
                for key, item in value.items()
            }
        return value

    def _replace_placeholders(self, value: str, message: NotificationMessage) -> str:
        replacements = {
            "title": message.notification_title,
            "content": message.content,
            "price": message.price,
            "reason": message.reason,
            "desktop_link": message.desktop_link,
            "mobile_link": message.mobile_link or message.desktop_link,
        }
        rendered = value
        for key, replacement in replacements.items():
            rendered = rendered.replace(f"${{{key}}}", replacement)
            rendered = rendered.replace(f"{{{{{key}}}}}", replacement)
        return rendered
