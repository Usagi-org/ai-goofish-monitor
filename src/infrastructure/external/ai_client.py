"""
AI 客户端封装
提供统一的 AI 调用接口
"""
import os
import json
import base64
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI
from src.infrastructure.config.settings import AISettings
from src.infrastructure.config.env_manager import env_manager


class AIClient:
    """AI 客户端封装"""

    def __init__(self):
        self.settings: Optional[AISettings] = None
        self.client: Optional[AsyncOpenAI] = None
        self.refresh()

    def _load_settings(self) -> None:
        load_dotenv(dotenv_path=env_manager.env_file, override=True)
        self.settings = AISettings()

    def refresh(self) -> None:
        self._load_settings()
        self.client = self._initialize_client()

    def _initialize_client(self) -> Optional[AsyncOpenAI]:
        """初始化 OpenAI 客户端"""
        if not self.settings or not self.settings.is_configured():
            print("警告：AI 配置不完整，AI 功能将不可用")
            return None

        try:
            if self.settings.proxy_url:
                print(f"正在为 AI 请求使用代理: {self.settings.proxy_url}")
                os.environ['HTTP_PROXY'] = self.settings.proxy_url
                os.environ['HTTPS_PROXY'] = self.settings.proxy_url

            return AsyncOpenAI(
                api_key=self.settings.api_key,
                base_url=self.settings.base_url
            )
        except Exception as e:
            print(f"初始化 AI 客户端失败: {e}")
            return None

    def is_available(self) -> bool:
        """检查 AI 客户端是否可用"""
        return self.client is not None

    @staticmethod
    def encode_image(image_path: str) -> Optional[str]:
        """将图片编码为 Base64"""
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"编码图片失败: {e}")
            return None

    async def analyze(
        self,
        product_data: Dict,
        image_paths: List[str],
        prompt_text: str
    ) -> Optional[Dict]:
        """
        分析商品数据

        Args:
            product_data: 商品数据
            image_paths: 图片路径列表
            prompt_text: 分析提示词

        Returns:
            分析结果
        """
        if not self.is_available():
            print("AI 客户端不可用")
            return None

        try:
            messages = self._build_messages(product_data, image_paths, prompt_text)
            response = await self._call_ai(messages)
            return self._parse_response(response)
        except Exception as e:
            print(f"AI 分析失败: {e}")
            return None

    def _build_messages(self, product_data: Dict, image_paths: List[str], prompt_text: str) -> List[Dict]:
        """构建 AI 消息"""
        product_json = json.dumps(product_data, ensure_ascii=False, indent=2)
        text_prompt = f"""请基于你的专业知识和我的要求，分析以下完整的商品JSON数据：

```json
{product_json}
```

{prompt_text}
"""
        user_content = []

        # 先添加图片
        for path in image_paths:
            base64_img = self.encode_image(path)
            if base64_img:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                })

        # 再添加文本
        user_content.append({"type": "text", "text": text_prompt})

        return [{"role": "user", "content": user_content}]

    async def _call_ai(self, messages: List[Dict]) -> str:
        """调用 AI API"""
        request_params = {
            "model": self.settings.model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4000
        }

        # 根据配置添加可选参数
        if self.settings.enable_response_format:
            request_params["response_format"] = {"type": "json_object"}

        if self.settings.enable_thinking:
            request_params["extra_body"] = {"enable_thinking": False}

        response = await self.client.chat.completions.create(**request_params)

        # 兼容不同 API 响应格式
        if hasattr(response, 'choices'):
            return response.choices[0].message.content
        return response

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """解析 AI 响应"""
        try:
            # 直接解析 JSON
            return json.loads(response_text)
        except json.JSONDecodeError:
            # 清理 Markdown 代码块标记
            cleaned = response_text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # 提取 JSON 对象
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = cleaned[start:end + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            print(f"无法解析 AI 响应: {response_text[:100]}")
            return None
