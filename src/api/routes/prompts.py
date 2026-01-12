"""
Prompt 管理路由
"""
import os
import aiofiles
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptUpdate(BaseModel):
    """Prompt 更新模型"""
    content: str


@router.get("")
async def list_prompts():
    """列出所有 prompt 文件"""
    prompts_dir = "prompts"
    if not os.path.isdir(prompts_dir):
        return []
    return [f for f in os.listdir(prompts_dir) if f.endswith(".txt")]


@router.get("/{filename}")
async def get_prompt(filename: str):
    """获取 prompt 文件内容"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    filepath = os.path.join("prompts", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到")

    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        content = await f.read()
    return {"filename": filename, "content": content}


@router.put("/{filename}")
async def update_prompt(
    filename: str,
    prompt_update: PromptUpdate,
):
    """更新 prompt 文件内容"""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    filepath = os.path.join("prompts", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt 文件未找到")

    try:
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(prompt_update.content)
        return {"message": f"Prompt 文件 '{filename}' 更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入文件时出错: {e}")
