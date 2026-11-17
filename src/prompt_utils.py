import json
import os
import re
import sys
from typing import Awaitable, Callable, Optional

import aiofiles

from src.infrastructure.external.ai_client import AIClient
from src.services.ai_output_schema import CRITERIA_SCHEMA, GeneratedCriteria
from src.services.ai_response_parser import parse_ai_response_json

# The meta-prompt to instruct the AI
META_PROMPT_TEMPLATE = r"""
你是一位世界级的AI提示词工程大师。你的任务是根据用户提供的【购买需求】，模仿一个【参考范例】，为闲鱼监控机器人的AI分析模块（代号 EagleEye）生成一份全新的【分析标准】文本。

你的输出必须严格遵循【参考范例】的结构、语气和核心原则，但内容要完全针对用户的【购买需求】进行定制。最终生成的文本将作为AI分析模块的思考指南。

---
这是【参考范例】（`macbook_criteria.txt`）：
```text
{reference_text}
```
---

这是用户的【购买需求】：
```text
{user_description}
```
---

请现在开始生成全新的【分析标准】文本。请注意：
1.  **只输出单个 JSON 对象**，仅包含字符串字段 `criteria`。把完整的分析标准正文放在该字段中，不输出思考过程、草稿或生成计划。
    正文必须以“第一部分：核心分析原则”章节开始，并包含“第二部分：详细分析指南”章节。
    JSON 示例：{{"criteria":"第一部分：核心分析原则\n...\n第二部分：详细分析指南\n..."}}
2.  保留范例中的 `[V6.3 核心升级]`、`[V6.4 逻辑修正]` 等版本标记，这有助于保持格式一致性。
3.  将范例中所有与 "MacBook" 相关的内容，替换为与用户需求商品相关的内容。
4.  生成针对新商品类型的“一票否决硬性原则”和“危险信号清单”。不要沿用购买需求没有提出的范例硬条件（例如必须邮寄、信用极好、拒绝商家等）。
5.  本次只生成筛选标准，商品分析的 JSON 字段格式由基础 Prompt 提供，不要在 criteria 内改写它。
6.  用户需求优先于参考范例，全文不得出现与需求相矛盾的否决条件。卖家画像必须基于实际提供的资料，不得假设能获取购买记录；图片也需核对真实性及是否对应同一商品，不能默认图片绝对可信。
"""

ProgressCallback = Callable[[str, str], Awaitable[None]]
# 参考标准大约一千多 token。思考模型还会先输出推理，800 会把正文截掉。
CRITERIA_MAX_OUTPUT_TOKENS = 16384
_THINK_BLOCK_RE = re.compile(
    r"<(?:think|thinking)>.*?</(?:think|thinking)>",
    re.IGNORECASE | re.DOTALL,
)
_UNCLOSED_THINK_RE = re.compile(r"<(?:think|thinking)>", re.IGNORECASE)


async def _report_progress(
    progress_callback: Optional[ProgressCallback],
    step_key: str,
    message: str,
) -> None:
    if progress_callback:
        await progress_callback(step_key, message)


def _read_reference_text(reference_file_path: str) -> str:
    try:
        with open(reference_file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"参考文件未找到: {reference_file_path}")
    except IOError as exc:
        raise IOError(f"读取参考文件失败: {exc}")


def _strip_reasoning_blocks(text: str) -> str:
    stripped = _THINK_BLOCK_RE.sub("", text).strip()
    if _UNCLOSED_THINK_RE.search(stripped):
        raise RuntimeError(
            "生成分析标准时，模型的思考过程占满了输出长度，正文被截断。"
            "请换一个不输出长思考过程的模型，或提高模型服务允许的输出长度。"
        )
    if not stripped:
        raise RuntimeError("AI 没有生成分析标准正文。")
    return stripped


async def _request_generated_text(ai_client: AIClient, prompt: str) -> str:
    print("正在调用AI生成新的分析标准，请稍候...")
    try:
        generated_text = await ai_client._call_ai(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_output_tokens=getattr(getattr(ai_client, "settings", None), "max_output_tokens", CRITERIA_MAX_OUTPUT_TOKENS),
            enable_json_output=True,
            json_schema=CRITERIA_SCHEMA,
            schema_name="generated_criteria",
        )
    except Exception as exc:
        print(f"调用 OpenAI API 时出错: {exc}")
        raise

    payload = GeneratedCriteria.model_validate(parse_ai_response_json(generated_text))
    generated_text = _strip_reasoning_blocks(payload.criteria)
    if not re.match(r"^(?:#{1,6}\s*)?(?:\*\*)?第一部分[：:]", generated_text) or not re.search(
        r"(?m)^(?:#{1,6}\s*)?(?:\*\*)?第二部分[：:]", generated_text
    ):
        raise ValueError("AI生成的分析标准缺少完整章节，可能返回了思考过程；未保存，请重新生成。")
    print("AI已成功生成内容。")
    return generated_text


async def _close_ai_client(
    ai_client: AIClient,
    active_error: BaseException | None,
) -> None:
    try:
        await ai_client.close()
    except Exception as close_error:
        print(f"关闭 AI 客户端时出错: {close_error}")
        if active_error is None:
            raise


async def generate_criteria(
    user_description: str,
    reference_file_path: str,
    progress_callback: Optional[ProgressCallback] = None,
) -> str:
    """
    Generates a new criteria file content using AI.
    """
    ai_client = AIClient()
    active_error: BaseException | None = None
    try:
        if not ai_client.is_available():
            ai_client.refresh()
        if not ai_client.is_available():
            raise RuntimeError("AI客户端未初始化，无法生成分析标准。请检查.env配置。")

        await _report_progress(progress_callback, "reference", "正在读取参考文件。")
        print(f"正在读取参考文件: {reference_file_path}")
        reference_text = _read_reference_text(reference_file_path)

        await _report_progress(progress_callback, "prompt", "正在构建发送给 AI 的指令。")
        print("正在构建发送给AI的指令...")
        prompt = META_PROMPT_TEMPLATE.format(
            reference_text=reference_text,
            user_description=user_description,
        )

        await _report_progress(progress_callback, "llm", "正在调用 AI 生成分析标准。")
        return await _request_generated_text(ai_client, prompt)
    except Exception as exc:
        active_error = exc
        raise
    finally:
        await _close_ai_client(ai_client, active_error)


async def update_config_with_new_task(new_task: dict, config_file: str = "config.json"):
    """
    将一个新任务添加到指定的JSON配置文件中。
    """
    print(f"正在更新配置文件: {config_file}")
    try:
        # 读取现有配置
        config_data = []
        if os.path.exists(config_file):
            async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                # 处理空文件的情况
                if content.strip():
                    try:
                        config_data = json.loads(content)
                        print(f"成功读取现有配置，当前任务数量: {len(config_data)}")
                    except json.JSONDecodeError as e:
                        print(f"解析配置文件失败，将创建新配置: {e}")
                        config_data = []
        else:
            print(f"配置文件不存在，将创建新文件: {config_file}")

        # 追加新任务
        config_data.append(new_task)

        # 写回配置文件
        async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config_data, ensure_ascii=False, indent=2))
            print(f"配置文件写入完成")

        print(f"成功！新任务 '{new_task.get('task_name')}' 已添加到 {config_file} 并已启用。")
        return True
    except json.JSONDecodeError as e:
        error_msg = f"错误: 配置文件 {config_file} 格式错误，无法解析: {e}"
        sys.stderr.write(error_msg + "\n")
        print(error_msg)
        return False
    except IOError as e:
        error_msg = f"错误: 读写配置文件失败: {e}"
        sys.stderr.write(error_msg + "\n")
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"错误: 更新配置文件时发生未知错误: {e}"
        sys.stderr.write(error_msg + "\n")
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        return False
