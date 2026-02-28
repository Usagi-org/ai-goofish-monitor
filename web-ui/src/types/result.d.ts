// Based on the data structure from web_server.py and scraper.py

export interface ProductInfo {
  "商品标题": string;
  "当前售价": string;
  "商品原价"?: string;
  "“想要”人数"?: string | number;
  "商品标签"?: string[];
  "发货地区"?: string;
  "卖家昵称"?: string;
  "商品链接": string;
  "发布时间"?: string;
  "商品ID": string;
  "商品图片列表"?: string[];
  "商品主图链接"?: string;
  "浏览量"?: string | number;
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
  "作为卖家的好评数"?: string;
  "作为卖家的好评率"?: string;
  "作为买家的好评数"?: string;
  "作为买家的好评率"?: string;
  "卖家发布的商品列表"?: any[]; // Define more strictly if needed
  "卖家收到的评价列表"?: any[]; // Define more strictly if needed
}

export interface AiAnalysis {
  is_recommended: boolean;
  reason: string;
  analysis_source?: 'ai' | 'keyword';
  keyword_hit_count?: number;
  prompt_version?: string;
  risk_tags?: string[];
  criteria_analysis?: Record<string, any>;
  matched_keywords?: string[];
  error?: string;
}

export interface ResultItem {
  "爬取时间": string;
  "搜索关键字": string;
  "任务名称": string;
  "商品信息": ProductInfo;
  "卖家信息": SellerInfo;
  ai_analysis: AiAnalysis;
}
