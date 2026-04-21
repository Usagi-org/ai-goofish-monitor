import asyncio
import sys
import os
import argparse
import json
import signal
import contextlib
import re
from datetime import datetime as dt

from src.config import get_state_file
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository
from src.scraper import scrape_xianyu, scrape_items_by_id_batch


async def main():
    parser = argparse.ArgumentParser(
        description="闲鱼商品监控脚本，支持多任务配置和实时 AI 分析。",
        epilog="""
使用示例:
  # 运行 config.json 中定义的所有任务
  python spider_v2.py

  # 只运行名为 "Sony A7M4" 的任务 (通常由调度器调用)
  python spider_v2.py --task-name "Sony A7M4"

  # 调试模式：运行所有任务，但每个任务只处理前 3 个新发现的商品
  python spider_v2.py --debug-limit 3
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--debug-limit", type=int, default=0, help="调试模式：每个任务仅处理前 N 个新商品（0 表示无限制）")
    parser.add_argument("--config", type=str, help="指定任务配置文件路径（传入时优先读取 JSON）")
    parser.add_argument("--task-name", type=str, help="只运行指定名称的单个任务 (用于定时任务调度)")
    args = parser.parse_args()

    if args.config:
        if not os.path.exists(args.config):
            sys.exit(f"错误：配置文件 '{args.config}' 不存在。")
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                tasks_config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            sys.exit(f"错误：读取或解析配置文件 '{args.config}' 失败：{e}")
    else:
        repository = SqliteTaskRepository()
        tasks = await repository.find_all()
        tasks_config = [task.model_dump() for task in tasks]

    def normalize_keywords(value):
        if value is None:
            return []
        if isinstance(value, str):
            raw_values = re.split(r"[\n,]+", value)
        elif isinstance(value, (list, tuple, set)):
            raw_values = list(value)
        else:
            raw_values = [value]

        normalized = []
        seen = set()
        for item in raw_values:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(text)
        return normalized

    def flatten_legacy_groups(groups):
        merged = []
        for group in groups or []:
            if isinstance(group, dict):
                merged.extend(normalize_keywords(group.get("include_keywords")))
        return normalize_keywords(merged)

    def has_bound_account(tasks: list) -> bool:
        for task in tasks:
            account = task.get("account_state_file")
            if isinstance(account, str) and account.strip():
                return True
        return False

    def has_any_state_file() -> bool:
        state_dir = os.getenv("ACCOUNT_STATE_DIR", "state").strip().strip('"').strip("'")
        if os.path.isdir(state_dir):
            for name in os.listdir(state_dir):
                if name.endswith(".json"):
                    return True
        return False

    state_file = get_state_file()
    if not os.path.exists(state_file) and not has_bound_account(tasks_config) and not has_any_state_file():
        sys.exit(
            f"错误：未找到登录状态文件。请在 state/ 中添加账号或配置 account_state_file。"
        )

    # 读取所有 prompt 文件内容（关键词模式不需要加载 prompt）
    for task in tasks_config:
        task_type = task.get("task_type", "keyword")
        decision_mode = str(task.get("decision_mode", "ai")).strip().lower()
        if decision_mode not in {"ai", "keyword"}:
            decision_mode = "ai"
        task["decision_mode"] = decision_mode

        # 商品 ID 监控模式的 prompt 处理
        if task_type == "item_id":
            keyword_rules = task.get("keyword_rules")
            if keyword_rules is None and task.get("keyword_rule_groups") is not None:
                task["keyword_rules"] = flatten_legacy_groups(task.get("keyword_rule_groups") or [])
            else:
                task["keyword_rules"] = normalize_keywords(keyword_rules)

            if decision_mode == "keyword":
                task["ai_prompt_text"] = ""
                continue

            if task.get("enabled", False) and task.get("ai_prompt_base_file") and task.get("ai_prompt_criteria_file"):
                try:
                    with open(task["ai_prompt_base_file"], 'r', encoding='utf-8') as f_base:
                        base_prompt = f_base.read()
                    with open(task["ai_prompt_criteria_file"], 'r', encoding='utf-8') as f_criteria:
                        criteria_text = f_criteria.read()

                    # 动态组合成最终的 Prompt
                    task['ai_prompt_text'] = base_prompt.replace("{{CRITERIA_SECTION}}", criteria_text)

                    # 验证生成的 prompt 是否有效
                    if len(task['ai_prompt_text']) < 100:
                        print(f"警告：任务 '{task['task_name']}' 生成的 prompt 过短 ({len(task['ai_prompt_text'])} 字符)，可能存在问题。")
                    elif "{{CRITERIA_SECTION}}" in task['ai_prompt_text']:
                        print(f"警告：任务 '{task['task_name']}' 的 prompt 中仍包含占位符，替换可能失败。")
                    else:
                        print(f"✅ 任务 '{task['task_name']}' 的 prompt 生成成功，长度：{len(task['ai_prompt_text'])} 字符")

                except FileNotFoundError as e:
                    print(f"警告：任务 '{task['task_name']}' 的 prompt 文件缺失：{e}，该任务的 AI 分析将被跳过。")
                    task['ai_prompt_text'] = ""
                except Exception as e:
                    print(f"错误：任务 '{task['task_name']}' 处理 prompt 文件时发生异常：{e}，该任务的 AI 分析将被跳过。")
                    task['ai_prompt_text'] = ""
        else:
            # 关键词搜索模式的 prompt 处理（原有逻辑）
            keyword_rules = task.get("keyword_rules")
            if keyword_rules is None and task.get("keyword_rule_groups") is not None:
                task["keyword_rules"] = flatten_legacy_groups(task.get("keyword_rule_groups") or [])
            else:
                task["keyword_rules"] = normalize_keywords(keyword_rules)

            if decision_mode == "keyword":
                task["ai_prompt_text"] = ""
                continue

            if task.get("enabled", False) and task.get("ai_prompt_base_file") and task.get("ai_prompt_criteria_file"):
                try:
                    with open(task["ai_prompt_base_file"], 'r', encoding='utf-8') as f_base:
                        base_prompt = f_base.read()
                    with open(task["ai_prompt_criteria_file"], 'r', encoding='utf-8') as f_criteria:
                        criteria_text = f_criteria.read()

                    # 动态组合成最终的 Prompt
                    task['ai_prompt_text'] = base_prompt.replace("{{CRITERIA_SECTION}}", criteria_text)

                    # 验证生成的 prompt 是否有效
                    if len(task['ai_prompt_text']) < 100:
                        print(f"警告：任务 '{task['task_name']}' 生成的 prompt 过短 ({len(task['ai_prompt_text'])} 字符)，可能存在问题。")
                    elif "{{CRITERIA_SECTION}}" in task['ai_prompt_text']:
                        print(f"警告：任务 '{task['task_name']}' 的 prompt 中仍包含占位符，替换可能失败。")
                    else:
                        print(f"✅ 任务 '{task['task_name']}' 的 prompt 生成成功，长度：{len(task['ai_prompt_text'])} 字符")

                except FileNotFoundError as e:
                    print(f"警告：任务 '{task['task_name']}' 的 prompt 文件缺失：{e}，该任务的 AI 分析将被跳过。")
                    task['ai_prompt_text'] = ""
                except Exception as e:
                    print(f"错误：任务 '{task['task_name']}' 处理 prompt 文件时发生异常：{e}，该任务的 AI 分析将被跳过。")
                    task['ai_prompt_text'] = ""
            elif task.get("enabled", False) and task.get("ai_prompt_file"):
                try:
                    with open(task["ai_prompt_file"], 'r', encoding='utf-8') as f:
                        task['ai_prompt_text'] = f.read()
                    print(f"✅ 任务 '{task['task_name']}' 的 prompt 文件读取成功，长度：{len(task['ai_prompt_text'])} 字符")
                except FileNotFoundError:
                    print(f"警告：任务 '{task['task_name']}' 的 prompt 文件 '{task['ai_prompt_file']}' 未找到，该任务的 AI 分析将被跳过。")
                    task['ai_prompt_text'] = ""
                except Exception as e:
                    print(f"错误：任务 '{task['task_name']}' 读取 prompt 文件时发生异常：{e}，该任务的 AI 分析将被跳过。")
                    task['ai_prompt_text'] = ""

    print("\n--- 开始执行监控任务 ---")
    if args.debug_limit > 0:
        print(f"** 调试模式已激活，每个任务最多处理 {args.debug_limit} 个新商品 **")

    if args.task_name:
        print(f"** 定时任务模式：只执行任务 '{args.task_name}' **")

    print("--------------------")

    # 记录爬虫开始时间（用于后续计算价格/想要数差异）
    crawl_start_time = dt.now().isoformat()

    active_task_configs = []
    if args.task_name:
        # 如果指定了任务名称，只查找该任务
        task_found = next((task for task in tasks_config if task.get('task_name') == args.task_name), None)
        if task_found:
            if task_found.get("enabled", False):
                active_task_configs.append(task_found)
            else:
                print(f"任务 '{args.task_name}' 已被禁用，跳过执行。")
        else:
            print(f"错误：在配置文件中未找到名为 '{args.task_name}' 的任务。")
            return
    else:
        # 否则，按原计划加载所有启用的任务
        active_task_configs = [task for task in tasks_config if task.get("enabled", False)]

    if not active_task_configs:
        print("没有需要执行的任务，程序退出。")
        return

    # 为每个启用的任务创建一个异步执行协程
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    tasks = []
    for task_conf in active_task_configs:
        task_type = task_conf.get("task_type", "keyword")
        if task_type == "item_id":
            # 商品 ID 监控任务
            print(f"-> 任务 '{task_conf['task_name']}' 已加入执行队列 (商品 ID 监控模式)。")
            item_ids = task_conf.get("item_id_list", [])
            if not item_ids:
                print(f"   警告：任务 '{task_conf['task_name']}' 未配置 item_id_list，跳过。")
                continue
            tasks.append(
                asyncio.create_task(
                    scrape_items_by_id_batch(
                        item_ids=item_ids,
                        task_config=task_conf,
                        debug_limit=args.debug_limit,
                    )
                )
            )
        else:
            # 关键词搜索任务
            print(f"-> 任务 '{task_conf['task_name']}' 已加入执行队列。")
            tasks.append(asyncio.create_task(scrape_xianyu(task_config=task_conf, debug_limit=args.debug_limit)))

    async def _shutdown_watcher():
        await stop_event.wait()
        print("\n收到终止信号，正在优雅退出，取消所有爬虫任务...")
        for t in tasks:
            if not t.done():
                t.cancel()

    shutdown_task = asyncio.create_task(_shutdown_watcher())

    try:
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        shutdown_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await shutdown_task

    print("\n--- 所有任务执行完毕 ---")
    executed_index = 0
    for i, task_conf in enumerate(active_task_configs):
        task_type = task_conf.get("task_type", "keyword")
        task_name = task_conf["task_name"]

        # 跳过未实际执行的任务（如 item_id 列表为空）
        if task_type == "item_id" and not task_conf.get("item_id_list", []):
            continue

        result = results[executed_index] if executed_index < len(results) else None
        executed_index += 1

        if isinstance(result, Exception):
            print(f"任务 '{task_name}' 因异常而终止：{result}")
        else:
            if task_type == "item_id":
                # 从数据库读取想要数和价格变化
                want_count_total = 0
                want_count_diff = 0
                price_diff = None
                try:
                    from src.services.metrics_tracking_service import get_metrics_service
                    metrics_service = get_metrics_service()
                    # 读取当前总想要数
                    want_count_total = metrics_service.get_total_want_count_for_task(task_name) or 0
                    # 读取上次和当前的想要数差异（只计算本次爬取开始后的变化）
                    want_count_diff = metrics_service.get_want_count_diff_for_task(task_name, since=crawl_start_time) or 0
                    # 读取价格变化（只计算本次爬取开始后的变化）
                    price_diff = metrics_service.get_price_diff_for_task(task_name, since=crawl_start_time)
                except Exception as e:
                    print(f"   获取指标数据失败：{e}")

                # 输出想要数和价格变化到日志（供 process_service.py 解析）
                if want_count_total > 0:
                    print(f"想要数：{want_count_total}")
                    if want_count_diff != 0:
                        print(f"上次想要数：{want_count_total - want_count_diff}")
                    print(f"推荐了 {result.get('processed_count', 0) if isinstance(result, dict) else result} 个商品")
                else:
                    print(f"任务 '{task_name}' 正常结束，本次运行共处理了 {result.get('processed_count', 0) if isinstance(result, dict) else result} 个商品。")

                if price_diff is not None and price_diff != 0:
                    price_sign = "+" if price_diff > 0 else ""
                    print(f"价格变化：¥{price_sign}{price_diff}")
            else:
                print(f"任务 '{task_name}' 正常结束，本次运行共处理了 {result} 个新商品。")

if __name__ == "__main__":
    asyncio.run(main())
