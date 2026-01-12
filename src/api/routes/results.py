"""
结果文件管理路由
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import List
import os
import glob
import json
import aiofiles


router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/files")
async def get_result_files():
    """获取所有结果文件列表"""
    # 主要从 jsonl 目录获取文件
    jsonl_dir = "jsonl"
    files = []

    if os.path.isdir(jsonl_dir):
        files = [f for f in os.listdir(jsonl_dir) if f.endswith(".jsonl")]

    # 返回格式与前端期望一致
    return {"files": files}


@router.get("/files/{filename:path}")
async def download_result_file(filename: str):
    """下载指定的结果文件"""
    # 安全检查：防止路径遍历攻击
    if ".." in filename or filename.startswith("/"):
        return {"error": "非法的文件路径"}

    # 文件在 jsonl 目录中
    file_path = os.path.join("jsonl", filename)

    if not os.path.exists(file_path) or not filename.endswith(".jsonl"):
        return {"error": "文件不存在"}

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/x-ndjson"
    )


@router.delete("/files/{filename:path}")
async def delete_result_file(filename: str):
    """删除指定的结果文件"""
    # 安全检查：防止路径遍历攻击
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="非法的文件路径")

    # 只允许删除 .jsonl 文件
    if not filename.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="只能删除 .jsonl 文件")

    # 文件在 jsonl 目录中
    file_path = os.path.join("jsonl", filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        os.remove(file_path)
        return {"message": f"文件 {filename} 已成功删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件时出错: {str(e)}")


@router.get("/{filename}")
async def get_result_file_content(
    filename: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    recommended_only: bool = Query(False),
    sort_by: str = Query("crawl_time"),
    sort_order: str = Query("desc"),
):
    """读取指定的 .jsonl 文件内容，支持分页、筛选和排序"""
    # 安全检查
    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    filepath = os.path.join("jsonl", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="结果文件未找到")

    results = []
    try:
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
            async for line in f:
                try:
                    record = json.loads(line)
                    if recommended_only:
                        if record.get("ai_analysis", {}).get("is_recommended") is True:
                            results.append(record)
                    else:
                        results.append(record)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取结果文件时出错: {e}")

    # 排序逻辑
    def get_sort_key(item):
        info = item.get("商品信息", {})
        if sort_by == "publish_time":
            return info.get("发布时间", "0000-00-00 00:00")
        elif sort_by == "price":
            price_str = str(info.get("当前售价", "0")).replace("¥", "").replace(",", "").strip()
            try:
                return float(price_str)
            except (ValueError, TypeError):
                return 0.0
        else:  # default to crawl_time
            return item.get("爬取时间", "")

    is_reverse = (sort_order == "desc")
    results.sort(key=get_sort_key, reverse=is_reverse)

    # 分页
    total_items = len(results)
    start = (page - 1) * limit
    end = start + limit
    paginated_results = results[start:end]

    return {
        "total_items": total_items,
        "page": page,
        "limit": limit,
        "items": paginated_results
    }
