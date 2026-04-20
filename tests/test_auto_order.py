"""
自动下单功能测试
"""
import pytest
from src.services.auto_order_service import AutoOrderService
from src.services.order_link_service import OrderLinkService


class TestOrderLinkService:
    """订单链接生成服务测试"""
    
    def test_generate_order_link(self):
        """测试生成订单链接"""
        service = OrderLinkService()
        link = service.generate_order_link(
            item_id="123456789",
            price="5000",
            seller_id="seller_001"
        )
        assert "itemId=123456789" in link
        assert "price=5000" in link
        assert "sellerId=seller_001" in link
        assert "goofish.com/order/confirm" in link
    
    def test_generate_order_link_without_seller(self):
        """测试生成不带卖家 ID 的订单链接"""
        service = OrderLinkService()
        link = service.generate_order_link(
            item_id="123456789",
            price="5000"
        )
        assert "itemId=123456789" in link
        assert "price=5000" in link
        assert "sellerId" not in link
    
    def test_generate_mobile_order_link(self):
        """测试生成移动端订单链接"""
        service = OrderLinkService()
        link = service.generate_mobile_order_link(
            item_id="123456789",
            price="5000"
        )
        assert "itemId=123456789" in link
        assert "price=5000" in link
        assert "m.goofish.com" in link


class TestAutoOrderService:
    """自动下单服务测试"""
    
    def test_check_price_match_with_target_price(self):
        """测试目标价格匹配"""
        service = AutoOrderService()
        
        # 价格低于目标价
        is_match, reason = service.check_price_match(
            item_price="4500",
            target_price="5000",
            min_price=None,
            max_price=None
        )
        assert is_match is True
        assert "已达到目标价" in reason
        
        # 价格等于目标价
        is_match, reason = service.check_price_match(
            item_price="5000",
            target_price="5000",
            min_price=None,
            max_price=None
        )
        assert is_match is True
        
        # 价格高于目标价
        is_match, reason = service.check_price_match(
            item_price="5500",
            target_price="5000",
            min_price=None,
            max_price=None
        )
        assert is_match is False
        assert "高于目标价" in reason
    
    def test_check_price_match_with_range(self):
        """测试价格区间匹配"""
        service = AutoOrderService()
        
        # 价格在区间内
        is_match, reason = service.check_price_match(
            item_price="4000",
            target_price=None,
            min_price="3000",
            max_price="5000"
        )
        assert is_match is True
        assert "在设定区间内" in reason
        
        # 价格低于最低价
        is_match, reason = service.check_price_match(
            item_price="2000",
            target_price=None,
            min_price="3000",
            max_price="5000"
        )
        assert is_match is False
        assert "低于最低价" in reason
        
        # 价格高于最高价
        is_match, reason = service.check_price_match(
            item_price="6000",
            target_price=None,
            min_price="3000",
            max_price="5000"
        )
        assert is_match is False
        assert "高于最高价" in reason
    
    def test_check_price_match_with_currency_symbol(self):
        """测试带货币符号的价格"""
        service = AutoOrderService()
        
        is_match, reason = service.check_price_match(
            item_price="¥5,000",
            target_price="5000",
            min_price=None,
            max_price=None
        )
        assert is_match is True
    
    def test_process_auto_order_notify_only(self):
        """测试仅通知模式"""
        service = AutoOrderService()
        item_data = {
            "商品 ID": "123456789",
            "当前售价": "4500",
            "商品链接": "https://example.com/item/123456789"
        }
        task_config = {
            "auto_order_enabled": True,
            "auto_order_action": "notify_only",
            "auto_order_target_price": "5000"
        }
        
        result = service.process_auto_order(item_data, task_config)
        
        assert result["should_notify"] is True
        assert result["order_link"] is None
        assert result["action_taken"] == "notify_only"
    
    def test_process_auto_order_generate_link(self):
        """测试生成链接模式"""
        service = AutoOrderService()
        item_data = {
            "商品 ID": "123456789",
            "当前售价": "4500",
            "商品链接": "https://example.com/item/123456789"
        }
        task_config = {
            "auto_order_enabled": True,
            "auto_order_action": "generate_link",
            "auto_order_target_price": "5000"
        }
        
        import asyncio
        result = asyncio.run(service.process_auto_order(item_data, task_config))
        
        assert result["should_notify"] is True
        assert result["order_link"] is not None
        assert result["action_taken"] == "link_generated"
    
    def test_process_auto_order_no_match(self):
        """测试价格不匹配"""
        service = AutoOrderService()
        item_data = {
            "商品 ID": "123456789",
            "当前售价": "6000",
            "商品链接": "https://example.com/item/123456789"
        }
        task_config = {
            "auto_order_enabled": True,
            "auto_order_action": "generate_link",
            "auto_order_target_price": "5000"
        }
        
        import asyncio
        result = asyncio.run(service.process_auto_order(item_data, task_config))
        
        assert result["should_notify"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
