export interface ResultItem {
  id: number;
  crawl_time: string;
  link: string;
  title: string;
  price: number;
  raw_json: string;
  is_ai_recommended: boolean;
  is_keyword_recommended: boolean;
  keyword_hit_count: number;
  publish_time?: string;
  seller_nickname?: string;
}

export interface RawResultItem extends Record<string, any> {
  "爬取时间"?: string;
  "商品信息"?: ProductInfo;
  "卖家信息"?: SellerInfo;
  "ai_analysis"?: AIAnalysis;
  "价格参考"?: PriceReference;
}

export interface ProductInfo {
  "商品 ID"?: string;
  "商品标题"?: string;
  "当前售价"?: string;
  "商品链接"?: string;
  "商品图片列表"?: string[];
  "发货地区"?: string;
  "卖家昵称"?: string;
  "发布时间"?: string;
  "想要"?: string;
  "浏览量"?: string;
  [key: string]: any;
}

export interface SellerInfo {
  "卖家昵称"?: string;
  "卖家头像链接"?: string;
  "卖家个性签名"?: string;
  "卖家在售/已售商品数"?: string;
  "卖家收到的评价总数"?: string;
  "卖家信用等级"?: string;
  "买家信用等级"?: string;
  "卖家芝麻信用"?: string;
  "卖家注册时长"?: string;
  "卖家最后活跃时间"?: string;
  "卖家活跃时间格式化"?: string;
  "卖家活跃等级"?: string;
  "卖家在线状态"?: string;
  "作为卖家的好评数"?: string;
  "作为卖家的好评率"?: string;
  "作为买家的好评数"?: string;
  "作为买家的好评率"?: string;
  "卖家发布的商品列表"?: any[];
  "卖家收到的评价列表"?: any[];
}

export interface AIAnalysis {
  analysis_source?: string;
  is_recommended?: boolean;
  reason?: string;
  keyword_hit_count?: number;
  risk_tags?: string[];
  [key: string]: any;
}

export interface PriceReference {
  "当前市场均价"?: string;
  "历史均价"?: string;
  "本商品价格位置"?: {
    "price_percentile"?: number;
    [key: string]: any;
  };
  [key: string]: any;
}
