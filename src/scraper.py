import asyncio
import json
import os
import random
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from playwright.async_api import (
    Response,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from src.ai_handler import (
    download_all_images,
    get_ai_analysis,
    send_ntfy_notification,
    cleanup_task_images,
)
from src.config import (
    AI_DEBUG_MODE,
    API_URL_PATTERN,
    DETAIL_API_URL_PATTERN,
    LOGIN_IS_EDGE,
    RUN_HEADLESS,
    RUNNING_IN_DOCKER,
    STATE_FILE,
)
from src.parsers import (
    _parse_search_results_json,
    _parse_user_items_data,
    calculate_reputation_from_ratings,
    parse_ratings_data,
    parse_user_head_data,
)
from src.utils import (
    format_registration_days,
    get_link_unique_key,
    random_sleep,
    safe_get,
    save_to_jsonl,
    log_time,
)
from src.rotation import RotationPool, load_state_files, parse_proxy_pool, RotationItem


class RiskControlError(Exception):
    pass


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_rotation_settings(task_config: dict) -> dict:
    account_cfg = task_config.get("account_rotation") or {}
    proxy_cfg = task_config.get("proxy_rotation") or {}

    account_enabled = _as_bool(account_cfg.get("enabled"), _as_bool(os.getenv("ACCOUNT_ROTATION_ENABLED"), False))
    account_mode = (account_cfg.get("mode") or os.getenv("ACCOUNT_ROTATION_MODE", "per_task")).lower()
    account_state_dir = account_cfg.get("state_dir") or os.getenv("ACCOUNT_STATE_DIR", "state")
    account_retry_limit = _as_int(account_cfg.get("retry_limit"), _as_int(os.getenv("ACCOUNT_ROTATION_RETRY_LIMIT"), 2))
    account_blacklist_ttl = _as_int(account_cfg.get("blacklist_ttl_sec"), _as_int(os.getenv("ACCOUNT_BLACKLIST_TTL"), 300))

    proxy_enabled = _as_bool(proxy_cfg.get("enabled"), _as_bool(os.getenv("PROXY_ROTATION_ENABLED"), False))
    proxy_mode = (proxy_cfg.get("mode") or os.getenv("PROXY_ROTATION_MODE", "per_task")).lower()
    proxy_pool = proxy_cfg.get("proxy_pool") or os.getenv("PROXY_POOL", "")
    proxy_retry_limit = _as_int(proxy_cfg.get("retry_limit"), _as_int(os.getenv("PROXY_ROTATION_RETRY_LIMIT"), 2))
    proxy_blacklist_ttl = _as_int(proxy_cfg.get("blacklist_ttl_sec"), _as_int(os.getenv("PROXY_BLACKLIST_TTL"), 300))

    return {
        "account_enabled": account_enabled,
        "account_mode": account_mode,
        "account_state_dir": account_state_dir,
        "account_retry_limit": max(1, account_retry_limit),
        "account_blacklist_ttl": max(0, account_blacklist_ttl),
        "proxy_enabled": proxy_enabled,
        "proxy_mode": proxy_mode,
        "proxy_pool": proxy_pool,
        "proxy_retry_limit": max(1, proxy_retry_limit),
        "proxy_blacklist_ttl": max(0, proxy_blacklist_ttl),
    }


def _default_context_options() -> dict:
    return {
        "user_agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "viewport": {"width": 412, "height": 915},
        "device_scale_factor": 2.625,
        "is_mobile": True,
        "has_touch": True,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "permissions": ["geolocation"],
        "geolocation": {"longitude": 121.4737, "latitude": 31.2304},
        "color_scheme": "light",
    }


def _clean_kwargs(options: dict) -> dict:
    return {k: v for k, v in options.items() if v is not None}


def _looks_like_mobile(ua: str) -> Optional[bool]:
    if not ua:
        return None
    ua_lower = ua.lower()
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        return True
    if "windows" in ua_lower or "macintosh" in ua_lower:
        return False
    return None


def _build_context_overrides(snapshot: dict) -> dict:
    env = snapshot.get("env") or {}
    headers = snapshot.get("headers") or {}
    navigator = env.get("navigator") or {}
    screen = env.get("screen") or {}
    intl = env.get("intl") or {}

    overrides = {}

    ua = headers.get("User-Agent") or headers.get("user-agent") or navigator.get("userAgent")
    if ua:
        overrides["user_agent"] = ua

    accept_language = headers.get("Accept-Language") or headers.get("accept-language")
    locale = None
    if accept_language:
        locale = accept_language.split(",")[0].strip()
    elif navigator.get("language"):
        locale = navigator["language"]
    if locale:
        overrides["locale"] = locale

    tz = intl.get("timeZone")
    if tz:
        overrides["timezone_id"] = tz

    width = screen.get("width")
    height = screen.get("height")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)):
        overrides["viewport"] = {"width": int(width), "height": int(height)}

    dpr = screen.get("devicePixelRatio")
    if isinstance(dpr, (int, float)):
        overrides["device_scale_factor"] = float(dpr)

    touch_points = navigator.get("maxTouchPoints")
    if isinstance(touch_points, (int, float)):
        overrides["has_touch"] = touch_points > 0

    mobile_flag = _looks_like_mobile(ua or "")
    if mobile_flag is not None:
        overrides["is_mobile"] = mobile_flag

    return _clean_kwargs(overrides)


def _build_extra_headers(raw_headers: Optional[dict]) -> dict:
    if not raw_headers:
        return {}
    excluded = {"cookie", "content-length"}
    headers = {}
    for key, value in raw_headers.items():
        if not key or key.lower() in excluded or value is None:
            continue
        headers[key] = value
    return headers


async def scrape_user_profile(context, user_id: str) -> dict:
    """
    【新版】访问指定用户的个人主页，按顺序采集其摘要信息、完整的商品列表和完整的评价列表。
    """
    print(f"   -> 开始采集用户ID: {user_id} 的完整信息...")
    profile_data = {}
    page = await context.new_page()

    # 为各项异步任务准备Future和数据容器
    head_api_future = asyncio.get_event_loop().create_future()

    all_items, all_ratings = [], []
    stop_item_scrolling, stop_rating_scrolling = asyncio.Event(), asyncio.Event()

    async def handle_response(response: Response):
        # 捕获头部摘要API
        if "mtop.idle.web.user.page.head" in response.url and not head_api_future.done():
            try:
                head_api_future.set_result(await response.json())
                print(f"      [API捕获] 用户头部信息... 成功")
            except Exception as e:
                if not head_api_future.done(): head_api_future.set_exception(e)

        # 捕获商品列表API
        elif "mtop.idle.web.xyh.item.list" in response.url:
            try:
                data = await response.json()
                all_items.extend(data.get('data', {}).get('cardList', []))
                print(f"      [API捕获] 商品列表... 当前已捕获 {len(all_items)} 件")
                if not data.get('data', {}).get('nextPage', True):
                    stop_item_scrolling.set()
            except Exception as e:
                stop_item_scrolling.set()

        # 捕获评价列表API
        elif "mtop.idle.web.trade.rate.list" in response.url:
            try:
                data = await response.json()
                all_ratings.extend(data.get('data', {}).get('cardList', []))
                print(f"      [API捕获] 评价列表... 当前已捕获 {len(all_ratings)} 条")
                if not data.get('data', {}).get('nextPage', True):
                    stop_rating_scrolling.set()
            except Exception as e:
                stop_rating_scrolling.set()

    page.on("response", handle_response)

    try:
        # --- 任务1: 导航并采集头部信息 ---
        await page.goto(f"https://www.goofish.com/personal?userId={user_id}", wait_until="domcontentloaded", timeout=20000)
        head_data = await asyncio.wait_for(head_api_future, timeout=15)
        profile_data = await parse_user_head_data(head_data)

        # --- 任务2: 滚动加载所有商品 (默认页面) ---
        print("      [采集阶段] 开始采集该用户的商品列表...")
        await random_sleep(2, 4) # 等待第一页商品API完成
        while not stop_item_scrolling.is_set():
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            try:
                await asyncio.wait_for(stop_item_scrolling.wait(), timeout=8)
            except asyncio.TimeoutError:
                print("      [滚动超时] 商品列表可能已加载完毕。")
                break
        profile_data["卖家发布的商品列表"] = await _parse_user_items_data(all_items)

        # --- 任务3: 点击并采集所有评价 ---
        print("      [采集阶段] 开始采集该用户的评价列表...")
        rating_tab_locator = page.locator("//div[text()='信用及评价']/ancestor::li")
        if await rating_tab_locator.count() > 0:
            await rating_tab_locator.click()
            await random_sleep(3, 5) # 等待第一页评价API完成

            while not stop_rating_scrolling.is_set():
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                try:
                    await asyncio.wait_for(stop_rating_scrolling.wait(), timeout=8)
                except asyncio.TimeoutError:
                    print("      [滚动超时] 评价列表可能已加载完毕。")
                    break

            profile_data['卖家收到的评价列表'] = await parse_ratings_data(all_ratings)
            reputation_stats = await calculate_reputation_from_ratings(all_ratings)
            profile_data.update(reputation_stats)
        else:
            print("      [警告] 未找到评价选项卡，跳过评价采集。")

    except Exception as e:
        print(f"   [错误] 采集用户 {user_id} 信息时发生错误: {e}")
    finally:
        page.remove_listener("response", handle_response)
        await page.close()
        print(f"   -> 用户 {user_id} 信息采集完成。")

    return profile_data


async def scrape_xianyu(task_config: dict, debug_limit: int = 0):
    """
    【核心执行器】
    根据单个任务配置，异步爬取闲鱼商品数据，并对每个新发现的商品进行实时的、独立的AI分析和通知。
    """
    keyword = task_config['keyword']
    max_pages = task_config.get('max_pages', 1)
    personal_only = task_config.get('personal_only', False)
    min_price = task_config.get('min_price')
    max_price = task_config.get('max_price')
    ai_prompt_text = task_config.get('ai_prompt_text', '')
    free_shipping = task_config.get('free_shipping', False)
    raw_new_publish = task_config.get('new_publish_option') or ''
    new_publish_option = raw_new_publish.strip()
    if new_publish_option == '__none__':
        new_publish_option = ''
    region_filter = (task_config.get('region') or '').strip()

    processed_links = set()
    output_filename = os.path.join("jsonl", f"{keyword.replace(' ', '_')}_full_data.jsonl")
    if os.path.exists(output_filename):
        print(f"LOG: 发现已存在文件 {output_filename}，正在加载历史记录以去重...")
        try:
            with open(output_filename, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        link = record.get('商品信息', {}).get('商品链接', '')
                        if link:
                            processed_links.add(get_link_unique_key(link))
                    except json.JSONDecodeError:
                        print(f"   [警告] 文件中有一行无法解析为JSON，已跳过。")
            print(f"LOG: 加载完成，已记录 {len(processed_links)} 个已处理过的商品。")
        except IOError as e:
            print(f"   [警告] 读取历史文件时发生错误: {e}")
    else:
        print(f"LOG: 输出文件 {output_filename} 不存在，将创建新文件。")

    rotation_settings = _get_rotation_settings(task_config)
    forced_account = task_config.get("account_state_file") or None
    if isinstance(forced_account, str) and not forced_account.strip():
        forced_account = None
    if forced_account:
        rotation_settings["account_enabled"] = False
    account_items = load_state_files(rotation_settings["account_state_dir"])
    if not forced_account and os.path.exists(STATE_FILE):
        account_items = [STATE_FILE]
    if not forced_account and not os.path.exists(STATE_FILE) and account_items:
        rotation_settings["account_enabled"] = True

    account_pool = RotationPool(account_items, rotation_settings["account_blacklist_ttl"], "account")
    proxy_pool = RotationPool(parse_proxy_pool(rotation_settings["proxy_pool"]), rotation_settings["proxy_blacklist_ttl"], "proxy")

    selected_account: Optional[RotationItem] = None
    selected_proxy: Optional[RotationItem] = None

    def _select_account(force_new: bool = False) -> Optional[RotationItem]:
        nonlocal selected_account
        if forced_account:
            return RotationItem(value=forced_account)
        if not rotation_settings["account_enabled"]:
            if os.path.exists(STATE_FILE):
                return RotationItem(value=STATE_FILE)
            return None
        if rotation_settings["account_mode"] == "per_task" and selected_account and not force_new:
            return selected_account
        picked = account_pool.pick_random()
        return picked or selected_account

    def _select_proxy(force_new: bool = False) -> Optional[RotationItem]:
        nonlocal selected_proxy
        if not rotation_settings["proxy_enabled"]:
            return None
        if rotation_settings["proxy_mode"] == "per_task" and selected_proxy and not force_new:
            return selected_proxy
        picked = proxy_pool.pick_random()
        return picked or selected_proxy

    async def _run_scrape_attempt(state_file: str, proxy_server: Optional[str]) -> int:
        processed_item_count = 0
        stop_scraping = False

        if not os.path.exists(state_file):
            raise FileNotFoundError(f"登录状态文件不存在: {state_file}")

        snapshot_data = None
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                snapshot_data = json.load(f)
        except Exception as e:
            print(f"警告：读取登录状态文件失败，将直接按路径使用: {e}")

        async with async_playwright() as p:
            # 反检测启动参数
            launch_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]

            launch_kwargs = {"headless": RUN_HEADLESS, "args": launch_args}
            if proxy_server:
                launch_kwargs["proxy"] = {"server": proxy_server}

            if LOGIN_IS_EDGE:
                launch_kwargs["channel"] = "msedge"
            else:
                if not RUNNING_IN_DOCKER:
                    launch_kwargs["channel"] = "chrome"

            browser = await p.chromium.launch(**launch_kwargs)

            context_kwargs = _default_context_options()
            storage_state_arg = state_file

            if isinstance(snapshot_data, dict):
                # 新版扩展导出的增强快照，包含环境和Header
                if any(key in snapshot_data for key in ("env", "headers", "page", "storage")):
                    print(f"检测到增强浏览器快照，应用环境参数: {state_file}")
                    storage_state_arg = {"cookies": snapshot_data.get("cookies", [])}
                    context_kwargs.update(_build_context_overrides(snapshot_data))
                    extra_headers = _build_extra_headers(snapshot_data.get("headers"))
                    if extra_headers:
                        context_kwargs["extra_http_headers"] = extra_headers
                else:
                    storage_state_arg = snapshot_data

            context_kwargs = _clean_kwargs(context_kwargs)
            context = await browser.new_context(storage_state=storage_state_arg, **context_kwargs)

            # 增强反检测脚本（模拟真实移动设备）
            await context.add_init_script("""
                // 移除webdriver标识
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                // 模拟真实移动设备的navigator属性
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});

                // 添加chrome对象
                window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}};

                // 模拟触摸支持
                Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 5});

                // 覆盖permissions查询（避免暴露自动化）
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                );
            """)

            page = await context.new_page()

            try:
                # 步骤 0 - 模拟真实用户：先访问首页（重要的反检测措施）
                log_time("步骤 0 - 模拟真实用户访问首页...")
                await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
                log_time("[反爬] 在首页停留，模拟浏览...")
                await random_sleep(1, 2)

                # 模拟随机滚动（移动设备的触摸滚动）
                await page.evaluate("window.scrollBy(0, Math.random() * 500 + 200)")
                await random_sleep(1, 2)

                log_time("步骤 1 - 导航到搜索结果页...")
                # 使用 'q' 参数构建正确的搜索URL，并进行URL编码
                params = {'q': keyword}
                search_url = f"https://www.goofish.com/search?{urlencode(params)}"
                log_time(f"目标URL: {search_url}")

                # 使用 expect_response 在导航的同时捕获初始搜索的API数据
                async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=30000) as response_info:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

                initial_response = await response_info.value

                # 等待页面加载出关键筛选元素，以确认已成功进入搜索结果页
                await page.wait_for_selector('text=新发布', timeout=15000)

                # 模拟真实用户行为：页面加载后的初始停留和浏览
                log_time("[反爬] 模拟用户查看页面...")
                await random_sleep(1, 3)

                # --- 新增：检查是否存在验证弹窗 ---
                baxia_dialog = page.locator("div.baxia-dialog-mask")
                middleware_widget = page.locator("div.J_MIDDLEWARE_FRAME_WIDGET")
                try:
                    # 等待弹窗在2秒内出现。如果出现，则执行块内代码。
                    await baxia_dialog.wait_for(state='visible', timeout=2000)
                    print("\n==================== CRITICAL BLOCK DETECTED ====================")
                    print("检测到闲鱼反爬虫验证弹窗 (baxia-dialog)，无法继续操作。")
                    print("这通常是因为操作过于频繁或被识别为机器人。")
                    print("建议：")
                    print("1. 停止脚本一段时间再试。")
                    print("2. (推荐) 在 .env 文件中设置 RUN_HEADLESS=false，以非无头模式运行，这有助于绕过检测。")
                    print(f"任务 '{keyword}' 将在此处中止。")
                    print("===================================================================")
                    raise RiskControlError("baxia-dialog")
                except PlaywrightTimeoutError:
                    # 2秒内弹窗未出现，这是正常情况，继续执行
                    pass

                # 检查是否有J_MIDDLEWARE_FRAME_WIDGET覆盖层
                try:
                    await middleware_widget.wait_for(state='visible', timeout=2000)
                    print("\n==================== CRITICAL BLOCK DETECTED ====================")
                    print("检测到闲鱼反爬虫验证弹窗 (J_MIDDLEWARE_FRAME_WIDGET)，无法继续操作。")
                    print("这通常是因为操作过于频繁或被识别为机器人。")
                    print("建议：")
                    print("1. 停止脚本一段时间再试。")
                    print("2. (推荐) 更新登录状态文件，确保登录状态有效。")
                    print("3. 降低任务执行频率，避免被识别为机器人。")
                    print(f"任务 '{keyword}' 将在此处中止。")
                    print("===================================================================")
                    raise RiskControlError("J_MIDDLEWARE_FRAME_WIDGET")
                except PlaywrightTimeoutError:
                    # 2秒内弹窗未出现，这是正常情况，继续执行
                    pass
                # --- 结束新增 ---

                try:
                    await page.click("div[class*='closeIconBg']", timeout=3000)
                    print("LOG: 已关闭广告弹窗。")
                except PlaywrightTimeoutError:
                    print("LOG: 未检测到广告弹窗。")

                final_response = None
                log_time("步骤 2 - 应用筛选条件...")
                if new_publish_option:
                    try:
                        await page.click('text=新发布')
                        await random_sleep(1, 2) # 原来是 (1.5, 2.5)
                        async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                            await page.click(f"text={new_publish_option}")
                            # --- 修改: 增加排序后的等待时间 ---
                            await random_sleep(2, 4) # 原来是 (3, 5)
                        final_response = await response_info.value
                    except PlaywrightTimeoutError:
                        log_time(f"新发布筛选 '{new_publish_option}' 请求超时，继续执行。")
                    except Exception as e:
                        print(f"LOG: 应用新发布筛选失败: {e}")

                if personal_only:
                    async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                        await page.click('text=个人闲置')
                        # --- 修改: 将固定等待改为随机等待，并加长 ---
                        await random_sleep(2, 4) # 原来是 asyncio.sleep(5)
                    final_response = await response_info.value

                if free_shipping:
                    try:
                        async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                            await page.click('text=包邮')
                            await random_sleep(2, 4)
                        final_response = await response_info.value
                    except PlaywrightTimeoutError:
                        log_time("包邮筛选请求超时，继续执行。")
                    except Exception as e:
                        print(f"LOG: 应用包邮筛选失败: {e}")

                if region_filter:
                    try:
                        area_trigger = page.get_by_text("区域", exact=True)
                        if await area_trigger.count():
                            await area_trigger.first.click()
                            await random_sleep(1.5, 2)
                            popover_candidates = page.locator("div.ant-popover")
                            popover = popover_candidates.filter(has=page.locator(".areaWrap--FaZHsn8E, [class*='areaWrap']")).last
                            if not await popover.count():
                                popover = popover_candidates.filter(has=page.get_by_text("重新定位")).last
                            if not await popover.count():
                                popover = popover_candidates.filter(has=page.get_by_text("查看")).last
                            if not await popover.count():
                                print("LOG: 未找到区域弹窗，跳过区域筛选。")
                                raise PlaywrightTimeoutError("region-popover-not-found")
                            await popover.wait_for(state="visible", timeout=5000)

                            # 列表容器：第一层 children 即省/市/区三列，不再强依赖具体类名，提升鲁棒性
                            area_wrap = popover.locator(".areaWrap--FaZHsn8E, [class*='areaWrap']").first
                            await area_wrap.wait_for(state="visible", timeout=3000)
                            columns = area_wrap.locator(":scope > div")
                            col_prov = columns.nth(0)
                            col_city = columns.nth(1)
                            col_dist = columns.nth(2)

                            region_parts = [p.strip() for p in region_filter.split('/') if p.strip()]

                            async def _click_in_column(column_locator, text_value: str, desc: str) -> None:
                                option = column_locator.locator(".provItem--QAdOx8nD", has_text=text_value).first
                                if await option.count():
                                    await option.click()
                                    await random_sleep(1.5, 2)
                                    try:
                                        await option.wait_for(state="attached", timeout=1500)
                                        await option.wait_for(state="visible", timeout=1500)
                                    except PlaywrightTimeoutError:
                                        pass
                                else:
                                    print(f"LOG: 未找到{desc} '{text_value}'，跳过。")

                            if len(region_parts) >= 1:
                                await _click_in_column(col_prov, region_parts[0], "省份")
                                await random_sleep(1, 2)
                            if len(region_parts) >= 2:
                                await _click_in_column(col_city, region_parts[1], "城市")
                                await random_sleep(1, 2)
                            if len(region_parts) >= 3:
                                await _click_in_column(col_dist, region_parts[2], "区/县")
                                await random_sleep(1, 2)

                            search_btn = popover.locator("div.searchBtn--Ic6RKcAb").first
                            if await search_btn.count():
                                try:
                                    async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                                        await search_btn.click()
                                        await random_sleep(2, 3)
                                    final_response = await response_info.value
                                except PlaywrightTimeoutError:
                                    log_time("区域筛选提交超时，继续执行。")
                            else:
                                print("LOG: 未找到区域弹窗的“查看XX件宝贝”按钮，跳过提交。")
                        else:
                            print("LOG: 未找到区域筛选触发器。")
                    except PlaywrightTimeoutError:
                        log_time(f"区域筛选 '{region_filter}' 请求超时，继续执行。")
                    except Exception as e:
                        print(f"LOG: 应用区域筛选 '{region_filter}' 失败: {e}")

                if min_price or max_price:
                    price_container = page.locator('div[class*="search-price-input-container"]').first
                    if await price_container.is_visible():
                        if min_price:
                            await price_container.get_by_placeholder("¥").first.fill(min_price)
                            # --- 修改: 将固定等待改为随机等待 ---
                            await random_sleep(1, 2.5) # 原来是 asyncio.sleep(5)
                        if max_price:
                            await price_container.get_by_placeholder("¥").nth(1).fill(max_price)
                            # --- 修改: 将固定等待改为随机等待 ---
                            await random_sleep(1, 2.5) # 原来是 asyncio.sleep(5)

                        async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                            await page.keyboard.press('Tab')
                            # --- 修改: 增加确认价格后的等待时间 ---
                            await random_sleep(2, 4) # 原来是 asyncio.sleep(5)
                        final_response = await response_info.value
                    else:
                        print("LOG: 警告 - 未找到价格输入容器。")

                log_time("所有筛选已完成，开始处理商品列表...")

                current_response = final_response if final_response and final_response.ok else initial_response
                for page_num in range(1, max_pages + 1):
                    if stop_scraping:
                        break
                    log_time(f"开始处理第 {page_num}/{max_pages} 页 ...")

                    if page_num > 1:
                        # 查找未被禁用的“下一页”按钮。闲鱼通过添加 'disabled' 类名来禁用按钮，而不是使用 disabled 属性。
                        next_btn = page.locator("[class*='search-pagination-arrow-right']:not([class*='disabled'])")
                        if not await next_btn.count():
                            log_time("已到达最后一页，未找到可用的‘下一页’按钮，停止翻页。")
                            break
                        try:
                            async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                                await next_btn.click()
                                # --- 修改: 增加翻页后的等待时间 ---
                                await random_sleep(2, 5) # 原来是 (1.5, 3.5)
                            current_response = await response_info.value
                        except PlaywrightTimeoutError:
                            log_time(f"翻页到第 {page_num} 页超时，停止翻页。")
                            break

                    if not (current_response and current_response.ok):
                        log_time(f"第 {page_num} 页响应无效，跳过。")
                        continue

                    basic_items = await _parse_search_results_json(await current_response.json(), f"第 {page_num} 页")
                    if not basic_items:
                        break

                    total_items_on_page = len(basic_items)
                    for i, item_data in enumerate(basic_items, 1):
                        if debug_limit > 0 and processed_item_count >= debug_limit:
                            log_time(f"已达到调试上限 ({debug_limit})，停止获取新商品。")
                            stop_scraping = True
                            break

                        unique_key = get_link_unique_key(item_data["商品链接"])
                        if unique_key in processed_links:
                            log_time(f"[页内进度 {i}/{total_items_on_page}] 商品 '{item_data['商品标题'][:20]}...' 已存在，跳过。")
                            continue

                        log_time(f"[页内进度 {i}/{total_items_on_page}] 发现新商品，获取详情: {item_data['商品标题'][:30]}...")
                        # --- 修改: 访问详情页前的等待时间，模拟用户在列表页上看了一会儿 ---
                        await random_sleep(2, 4) # 原来是 (2, 4)

                        detail_page = await context.new_page()
                        try:
                            async with detail_page.expect_response(lambda r: DETAIL_API_URL_PATTERN in r.url, timeout=25000) as detail_info:
                                await detail_page.goto(item_data["商品链接"], wait_until="domcontentloaded", timeout=25000)

                            detail_response = await detail_info.value
                            if detail_response.ok:
                                detail_json = await detail_response.json()

                                ret_string = str(await safe_get(detail_json, 'ret', default=[]))
                                if "FAIL_SYS_USER_VALIDATE" in ret_string:
                                    print("\n==================== CRITICAL BLOCK DETECTED ====================")
                                    print("检测到闲鱼反爬虫验证 (FAIL_SYS_USER_VALIDATE)，程序将终止。")
                                    long_sleep_duration = random.randint(3, 60)
                                    print(f"为避免账户风险，将执行一次长时间休眠 ({long_sleep_duration} 秒) 后再退出...")
                                    await asyncio.sleep(long_sleep_duration)
                                    print("长时间休眠结束，现在将安全退出。")
                                    print("===================================================================")
                                    raise RiskControlError("FAIL_SYS_USER_VALIDATE")

                                # 解析商品详情数据并更新 item_data
                                item_do = await safe_get(detail_json, 'data', 'itemDO', default={})
                                seller_do = await safe_get(detail_json, 'data', 'sellerDO', default={})

                                reg_days_raw = await safe_get(seller_do, 'userRegDay', default=0)
                                registration_duration_text = format_registration_days(reg_days_raw)

                                # --- START: 新增代码块 ---

                                # 1. 提取卖家的芝麻信用信息
                                zhima_credit_text = await safe_get(seller_do, 'zhimaLevelInfo', 'levelName')

                                # 2. 提取该商品的完整图片列表
                                image_infos = await safe_get(item_do, 'imageInfos', default=[])
                                if image_infos:
                                    # 使用列表推导式获取所有有效的图片URL
                                    all_image_urls = [img.get('url') for img in image_infos if img.get('url')]
                                    if all_image_urls:
                                        # 用新的字段存储图片列表，替换掉旧的单个链接
                                        item_data['商品图片列表'] = all_image_urls
                                        # (可选) 仍然保留主图链接，以防万一
                                        item_data['商品主图链接'] = all_image_urls[0]

                                # --- END: 新增代码块 ---
                                item_data['“想要”人数'] = await safe_get(item_do, 'wantCnt', default=item_data.get('“想要”人数', 'NaN'))
                                item_data['浏览量'] = await safe_get(item_do, 'browseCnt', default='-')
                                # ...[此处可添加更多从详情页解析出的商品信息]...

                                # 调用核心函数采集卖家信息
                                user_profile_data = {}
                                user_id = await safe_get(seller_do, 'sellerId')
                                if user_id:
                                    # 新的、高效的调用方式:
                                    user_profile_data = await scrape_user_profile(context, str(user_id))
                                else:
                                    print("   [警告] 未能从详情API中获取到卖家ID。")
                                user_profile_data['卖家芝麻信用'] = zhima_credit_text
                                user_profile_data['卖家注册时长'] = registration_duration_text

                                # 构建基础记录
                                final_record = {
                                    "爬取时间": datetime.now().isoformat(),
                                    "搜索关键字": keyword,
                                    "任务名称": task_config.get('task_name', 'Untitled Task'),
                                    "商品信息": item_data,
                                    "卖家信息": user_profile_data
                                }

                                # --- START: Real-time AI Analysis & Notification ---
                                from src.config import SKIP_AI_ANALYSIS

                                # 检查是否跳过AI分析并直接发送通知
                                if SKIP_AI_ANALYSIS:
                                    log_time("环境变量 SKIP_AI_ANALYSIS 已设置，跳过AI分析并直接发送通知...")
                                    # 下载图片
                                    image_urls = item_data.get('商品图片列表', [])
                                    downloaded_image_paths = await download_all_images(item_data['商品ID'], image_urls, task_config.get('task_name', 'default'))

                                    # 删除下载的图片文件，节省空间
                                    for img_path in downloaded_image_paths:
                                        try:
                                            if os.path.exists(img_path):
                                                os.remove(img_path)
                                                print(f"   [图片] 已删除临时图片文件: {img_path}")
                                        except Exception as e:
                                            print(f"   [图片] 删除图片文件时出错: {e}")

                                    # 直接发送通知，将所有商品标记为推荐
                                    log_time("商品已跳过AI分析，准备发送通知...")
                                    await send_ntfy_notification(item_data, "商品已跳过AI分析，直接通知")
                                else:
                                    log_time(f"开始对商品 #{item_data['商品ID']} 进行实时AI分析...")
                                    # 1. Download images
                                    image_urls = item_data.get('商品图片列表', [])
                                    downloaded_image_paths = await download_all_images(item_data['商品ID'], image_urls, task_config.get('task_name', 'default'))

                                    # 2. Get AI analysis
                                    ai_analysis_result = None
                                    if ai_prompt_text:
                                        try:
                                            # 注意：这里我们将整个记录传给AI，让它拥有最全的上下文
                                            ai_analysis_result = await get_ai_analysis(final_record, downloaded_image_paths, prompt_text=ai_prompt_text)
                                            if ai_analysis_result:
                                                final_record['ai_analysis'] = ai_analysis_result
                                                log_time(f"AI分析完成。推荐状态: {ai_analysis_result.get('is_recommended')}")
                                            else:
                                                final_record['ai_analysis'] = {'error': 'AI analysis returned None after retries.'}
                                        except Exception as e:
                                            print(f"   -> AI分析过程中发生严重错误: {e}")
                                            final_record['ai_analysis'] = {'error': str(e)}
                                    else:
                                        print("   -> 任务未配置AI prompt，跳过分析。")

                                    # 删除下载的图片文件，节省空间
                                    for img_path in downloaded_image_paths:
                                        try:
                                            if os.path.exists(img_path):
                                                os.remove(img_path)
                                                print(f"   [图片] 已删除临时图片文件: {img_path}")
                                        except Exception as e:
                                            print(f"   [图片] 删除图片文件时出错: {e}")

                                    # 3. Send notification if recommended
                                    if ai_analysis_result and ai_analysis_result.get('is_recommended'):
                                        log_time("商品被AI推荐，准备发送通知...")
                                        await send_ntfy_notification(item_data, ai_analysis_result.get("reason", "无"))
                                # --- END: Real-time AI Analysis & Notification ---

                                # 4. 保存包含AI结果的完整记录
                                await save_to_jsonl(final_record, keyword)

                                processed_links.add(unique_key)
                                processed_item_count += 1
                                log_time(f"商品处理流程完毕。累计处理 {processed_item_count} 个新商品。")

                                # --- 修改: 增加单个商品处理后的主要延迟 ---
                                log_time("[反爬] 执行一次主要的随机延迟以模拟用户浏览间隔...")
                                await random_sleep(5, 10)
                            else:
                                print(f"   错误: 获取商品详情API响应失败，状态码: {detail_response.status}")
                                if AI_DEBUG_MODE:
                                    print(f"--- [DETAIL DEBUG] FAILED RESPONSE from {item_data['商品链接']} ---")
                                    try:
                                        print(await detail_response.text())
                                    except Exception as e:
                                        print(f"无法读取响应内容: {e}")
                                    print("----------------------------------------------------")

                        except PlaywrightTimeoutError:
                            print(f"   错误: 访问商品详情页或等待API响应超时。")
                        except Exception as e:
                            print(f"   错误: 处理商品详情时发生未知错误: {e}")
                        finally:
                            await detail_page.close()
                            # --- 修改: 增加关闭页面后的短暂整理时间 ---
                            await random_sleep(2, 4) # 原来是 (1, 2.5)

                    # --- 新增: 在处理完一页所有商品后，翻页前，增加一个更长的“休息”时间 ---
                    if not stop_scraping and page_num < max_pages:
                        print(f"--- 第 {page_num} 页处理完毕，准备翻页。执行一次页面间的长时休息... ---")
                        await random_sleep(10, 15)

            except PlaywrightTimeoutError as e:
                print(f"\n操作超时错误: 页面元素或网络响应未在规定时间内出现。\n{e}")
                raise
            except asyncio.CancelledError:
                log_time("收到取消信号，正在终止当前爬虫任务...")
                raise
            except Exception as e:
                if type(e).__name__ == "TargetClosedError":
                    log_time("浏览器已关闭，忽略后续异常（可能是任务被停止）。")
                    return processed_item_count
                print(f"\n爬取过程中发生未知错误: {e}")
                raise
            finally:
                log_time("任务执行完毕，浏览器将在5秒后自动关闭...")
                await asyncio.sleep(5)
                if debug_limit:
                    input("按回车键关闭浏览器...")
                await browser.close()

        return processed_item_count

    processed_item_count = 0
    attempt_limit = max(rotation_settings["account_retry_limit"], rotation_settings["proxy_retry_limit"], 1)
    last_error = ""

    for attempt in range(1, attempt_limit + 1):
        if attempt == 1:
            selected_account = _select_account()
            selected_proxy = _select_proxy()
        else:
            if rotation_settings["account_enabled"] and rotation_settings["account_mode"] == "on_failure":
                account_pool.mark_bad(selected_account, last_error)
                selected_account = _select_account(force_new=True)
            if rotation_settings["proxy_enabled"] and rotation_settings["proxy_mode"] == "on_failure":
                proxy_pool.mark_bad(selected_proxy, last_error)
                selected_proxy = _select_proxy(force_new=True)

        if rotation_settings["account_enabled"] and not selected_account:
            print("未找到可用的登录状态文件，无法继续执行任务。")
            break
        if not rotation_settings["account_enabled"] and not selected_account:
            print("未找到可用的登录状态文件，无法继续执行任务。")
            break
        if rotation_settings["proxy_enabled"] and not selected_proxy:
            print("未找到可用的代理地址，无法继续执行任务。")
            break

        state_path = selected_account.value if selected_account else STATE_FILE
        proxy_server = selected_proxy.value if selected_proxy else None
        if rotation_settings["account_enabled"]:
            print(f"账号轮换：使用登录状态 {state_path}")
        if rotation_settings["proxy_enabled"] and proxy_server:
            print(f"IP 轮换：使用代理 {proxy_server}")

        try:
            processed_item_count += await _run_scrape_attempt(state_path, proxy_server)
            break
        except RiskControlError as e:
            last_error = str(e)
            print(f"检测到风控或验证触发: {e}")
            if attempt < attempt_limit:
                print("将尝试轮换账号/IP 后重试...")
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"本次尝试失败: {last_error}")
            if attempt < attempt_limit:
                print("将尝试轮换账号/IP 后重试...")

    # 清理任务图片目录
    cleanup_task_images(task_config.get('task_name', 'default'))

    return processed_item_count
