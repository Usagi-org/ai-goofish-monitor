from dataclasses import dataclass
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError


@dataclass(frozen=True)
class SearchFilterOptions:
    new_publish_option: str = ""
    personal_only: bool = False
    free_shipping: bool = False
    region_filter: str = ""
    min_price: Any = None
    max_price: Any = None

    @classmethod
    def from_runtime_config(cls, runtime_config) -> "SearchFilterOptions":
        return cls(
            new_publish_option=runtime_config.new_publish_option,
            personal_only=runtime_config.personal_only,
            free_shipping=runtime_config.free_shipping,
            region_filter=runtime_config.region_filter,
            min_price=runtime_config.min_price,
            max_price=runtime_config.max_price,
        )


def parse_region_parts(region_filter: str) -> list[str]:
    return [p.strip() for p in region_filter.split("/") if p.strip()]


async def apply_search_filters(
    page,
    options: SearchFilterOptions,
    *,
    response_predicate,
    random_sleep,
    log_time,
) -> object | None:
    final_response = None
    log_time("步骤 2 - 应用筛选条件...")
    if options.new_publish_option:
        try:
            await page.click("text=新发布")
            await random_sleep(1, 2)  # 原来是 (1.5, 2.5)
            async with page.expect_response(
                response_predicate, timeout=20000
            ) as response_info:
                await page.click(f"text={options.new_publish_option}")
                # --- 修改: 增加排序后的等待时间 ---
                await random_sleep(2, 4)  # 原来是 (3, 5)
            final_response = await response_info.value
        except PlaywrightTimeoutError:
            log_time(f"新发布筛选 '{options.new_publish_option}' 请求超时，继续执行。")
        except Exception as e:
            print(f"LOG: 应用新发布筛选失败: {e}")

    if options.personal_only:
        async with page.expect_response(
            response_predicate, timeout=20000
        ) as response_info:
            await page.click("text=个人闲置")
            # --- 修改: 将固定等待改为随机等待，并加长 ---
            await random_sleep(2, 4)  # 原来是 asyncio.sleep(5)
        final_response = await response_info.value

    if options.free_shipping:
        try:
            async with page.expect_response(
                response_predicate, timeout=20000
            ) as response_info:
                await page.click("text=包邮")
                await random_sleep(2, 4)
            final_response = await response_info.value
        except PlaywrightTimeoutError:
            log_time("包邮筛选请求超时，继续执行。")
        except Exception as e:
            print(f"LOG: 应用包邮筛选失败: {e}")

    if options.region_filter:
        try:
            area_trigger = page.get_by_text("区域", exact=True)
            if await area_trigger.count():
                await area_trigger.first.click()
                await random_sleep(1.5, 2)
                popover_candidates = page.locator("div.ant-popover")
                popover = popover_candidates.filter(
                    has=page.locator(".areaWrap--FaZHsn8E, [class*='areaWrap']")
                ).last
                if not await popover.count():
                    popover = popover_candidates.filter(
                        has=page.get_by_text("重新定位")
                    ).last
                if not await popover.count():
                    popover = popover_candidates.filter(
                        has=page.get_by_text("查看")
                    ).last
                if not await popover.count():
                    print("LOG: 未找到区域弹窗，跳过区域筛选。")
                    raise PlaywrightTimeoutError("region-popover-not-found")
                await popover.wait_for(state="visible", timeout=5000)

                # 列表容器：第一层 children 即省/市/区三列，不再强依赖具体类名，提升鲁棒性
                area_wrap = popover.locator(
                    ".areaWrap--FaZHsn8E, [class*='areaWrap']"
                ).first
                await area_wrap.wait_for(state="visible", timeout=3000)
                columns = area_wrap.locator(":scope > div")
                col_prov = columns.nth(0)
                col_city = columns.nth(1)
                col_dist = columns.nth(2)

                region_parts = parse_region_parts(options.region_filter)

                async def _click_in_column(
                    column_locator, text_value: str, desc: str
                ) -> None:
                    option = column_locator.locator(
                        ".provItem--QAdOx8nD", has_text=text_value
                    ).first
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
                        async with page.expect_response(
                            response_predicate,
                            timeout=20000,
                        ) as response_info:
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
            log_time(f"区域筛选 '{options.region_filter}' 请求超时，继续执行。")
        except Exception as e:
            print(f"LOG: 应用区域筛选 '{options.region_filter}' 失败: {e}")

    if options.min_price or options.max_price:
        price_container = page.locator(
            'div[class*="search-price-input-container"]'
        ).first
        if await price_container.is_visible():
            if options.min_price:
                await price_container.get_by_placeholder("¥").first.fill(
                    options.min_price
                )
                # --- 修改: 将固定等待改为随机等待 ---
                await random_sleep(1, 2.5)  # 原来是 asyncio.sleep(5)
            if options.max_price:
                await (
                    price_container.get_by_placeholder("¥")
                    .nth(1)
                    .fill(options.max_price)
                )
                # --- 修改: 将固定等待改为随机等待 ---
                await random_sleep(1, 2.5)  # 原来是 asyncio.sleep(5)

            async with page.expect_response(
                response_predicate, timeout=20000
            ) as response_info:
                await page.keyboard.press("Tab")
                # --- 修改: 增加确认价格后的等待时间 ---
                await random_sleep(2, 4)  # 原来是 asyncio.sleep(5)
            final_response = await response_info.value
        else:
            print("LOG: 警告 - 未找到价格输入容器。")

    return final_response
