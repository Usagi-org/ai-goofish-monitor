"""
订单链接生成服务
生成闲鱼商品的一键下单链接
"""
from typing import Optional
from urllib.parse import urlencode


class OrderLinkService:
    """订单链接生成服务"""
    
    @staticmethod
    def generate_order_link(
        item_id: str,
        price: str,
        seller_id: Optional[str] = None,
        source: str = "monitor"
    ) -> str:
        """
        生成闲鱼商品一键下单链接
        
        Args:
            item_id: 商品 ID
            price: 商品价格
            seller_id: 卖家 ID（可选）
            source: 来源标识
            
        Returns:
            下单链接 URL
        """
        base_url = "https://www.goofish.com/order/confirm"
        
        # 构建订单确认页面的参数
        params = {
            "itemId": item_id,
            "price": str(price),
            "source": source,
        }
        
        if seller_id:
            params["sellerId"] = seller_id
        
        query_string = urlencode(params)
        return f"{base_url}?{query_string}"
    
    @staticmethod
    def generate_mobile_order_link(
        item_id: str,
        price: str,
        seller_id: Optional[str] = None
    ) -> str:
        """
        生成移动端下单链接（使用闲鱼 app schema）
        
        Args:
            item_id: 商品 ID
            price: 商品价格
            seller_id: 卖家 ID（可选）
            
        Returns:
            移动端下单链接
        """
        # 闲鱼移动端使用 tbopen:// schema 或者 goofish://
        base_url = "https://m.goofish.com/order/confirm"
        
        params = {
            "itemId": item_id,
            "price": str(price),
        }
        
        if seller_id:
            params["sellerId"] = seller_id
        
        query_string = urlencode(params)
        return f"{base_url}?{query_string}"
    
    @staticmethod
    def generate_direct_buy_link(
        item_link: str,
        action: str = "buy"
    ) -> str:
        """
        在商品链接基础上生成直接购买链接
        
        Args:
            item_link: 原始商品链接
            action: 操作类型 (buy, cart, offer)
            
        Returns:
            带有购买动作的链接
        """
        # 如果已有商品链接，直接返回，用户需要手动点击购买
        # 闲鱼不支持通过 URL 参数直接跳转到支付页面
        return item_link
