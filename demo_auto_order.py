#!/usr/bin/env python3
"""
自动下单功能演示脚本

演示如何使用自动下单功能监控商品并生成下单链接
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.services.auto_order_service import AutoOrderService
from src.services.order_link_service import OrderLinkService


def demo_order_link_generation():
    """演示订单链接生成"""
    print("=" * 60)
    print("演示 1: 生成闲鱼订单链接")
    print("=" * 60)
    
    link_service = OrderLinkService()
    
    # 示例商品数据
    item = {
        "商品 ID": "686123456789",
        "商品标题": "iPhone 15 Pro Max 256G 蓝色钛金属 99 新",
        "当前售价": "8999",
        "商品链接": "https://www.goofish.com/item/686123456789.htm"
    }
    
    # 生成 PC 端链接
    pc_link = link_service.generate_order_link(
        item_id=item["商品 ID"],
        price=item["当前售价"],
        source="monitor"
    )
    
    # 生成移动端链接
    mobile_link = link_service.generate_mobile_order_link(
        item_id=item["商品 ID"],
        price=item["当前售价"]
    )
    
    print(f"\n商品：{item['商品标题']}")
    print(f"价格：¥{item['当前售价']}")
    print(f"\nPC 端下单链接:")
    print(f"  {pc_link}")
    print(f"\n移动端下单链接:")
    print(f"  {mobile_link}")
    print()


def demo_price_matching():
    """演示价格匹配检测"""
    print("=" * 60)
    print("演示 2: 价格匹配检测")
    print("=" * 60)
    
    service = AutoOrderService()
    
    test_cases = [
        {
            "name": "测试 1: 价格低于目标价",
            "item_price": "4500",
            "target_price": "5000",
            "min_price": None,
            "max_price": None,
        },
        {
            "name": "测试 2: 价格等于目标价",
            "item_price": "5000",
            "target_price": "5000",
            "min_price": None,
            "max_price": None,
        },
        {
            "name": "测试 3: 价格高于目标价",
            "item_price": "5500",
            "target_price": "5000",
            "min_price": None,
            "max_price": None,
        },
        {
            "name": "测试 4: 价格在区间内",
            "item_price": "4000",
            "target_price": None,
            "min_price": "3000",
            "max_price": "5000",
        },
        {
            "name": "测试 5: 带货币符号的价格",
            "item_price": "¥5,000",
            "target_price": "5000",
            "min_price": None,
            "max_price": None,
        },
    ]
    
    for case in test_cases:
        is_match, reason = service.check_price_match(
            item_price=case["item_price"],
            target_price=case["target_price"],
            min_price=case["min_price"],
            max_price=case["max_price"],
        )
        status = "✓ 匹配" if is_match else "✗ 不匹配"
        print(f"\n{case['name']}")
        print(f"  价格：{case['item_price']}")
        print(f"  结果：{status}")
        print(f"  原因：{reason}")
    
    print()


async def demo_auto_order_processing():
    """演示完整的自动下单处理流程"""
    print("=" * 60)
    print("演示 3: 自动下单处理流程")
    print("=" * 60)
    
    service = AutoOrderService()
    
    # 示例商品数据
    item_data = {
        "商品 ID": "686123456789",
        "商品标题": "MacBook Pro 2023 M3 14 寸",
        "当前售价": "12999",
        "商品链接": "https://www.goofish.com/item/686123456789.htm",
    }
    
    # 任务配置：启用自动下单，目标价 13000
    task_config = {
        "auto_order_enabled": True,
        "auto_order_action": "generate_link",
        "auto_order_target_price": "13000",
    }
    
    print(f"\n商品：{item_data['商品标题']}")
    print(f"价格：¥{item_data['当前售价']}")
    print(f"目标价：¥{task_config['auto_order_target_price']}")
    print()
    
    # 处理自动下单
    result = await service.process_auto_order(
        item_data=item_data,
        task_config=task_config,
    )
    
    print(f"处理结果:")
    print(f"  是否通知：{result['should_notify']}")
    print(f"  操作类型：{result['action_taken']}")
    print(f"  原因：{result['reason']}")
    
    if result.get("order_link"):
        print(f"\n  PC 端下单链接:")
        print(f"    {result['order_link']}")
    
    if result.get("mobile_order_link"):
        print(f"\n  移动端下单链接:")
        print(f"    {result['mobile_order_link']}")
    
    print()


async def main():
    """主函数"""
    print("\n")
    print("★" * 30 + " 自动下单功能演示 " + "★" * 30)
    print()
    
    # 演示 1: 订单链接生成
    demo_order_link_generation()
    
    # 演示 2: 价格匹配检测
    demo_price_matching()
    
    # 演示 3: 完整处理流程
    await demo_auto_order_processing()
    
    print("=" * 60)
    print("演示完成!")
    print("=" * 60)
    print()
    print("使用说明:")
    print("1. 在 Web UI 创建任务时启用'自动下单'选项")
    print("2. 设置目标价格或价格区间")
    print("3. 选择下单操作：仅通知/生成链接/自动购买")
    print("4. 当价格匹配时，系统会自动发送带下单链接的通知")
    print()


if __name__ == "__main__":
    asyncio.run(main())
