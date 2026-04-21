export interface SellerInfo {
  seller_id: string
  seller_nickname: string
  seller_avatar: string
  zhima_credit: string
  registration_days: number
  good_rate: string
  total_items: number
  total_ratings: number
  last_updated: string
}

export interface SellerListResponse {
  seller_id: string
  list_type: 'blacklist' | 'whitelist'
  reason: string
  created_at: string
  expires_at: string | null
}

export interface MetricsSnapshot {
  price: number | null
  price_display: string | null
  want_count: number | null
  browse_count: number | null
  snapshot_time: string
}

export interface PriceHistoryPoint {
  time: string
  price: number | null
  price_display: string | null
}

export interface WantCountHistoryPoint {
  time: string
  want_count: number | null
}

export interface ItemSearchResult {
  '商品标题': string
  '当前售价': string
  '商品原价': string | null
  '想要人数': number | string | null
  '商品标签': string[]
  '发货地区': string
  '卖家昵称': string
  '商品链接': string
  '发布时间': string | null
  '商品 ID': string
}

export interface SearchHistoryItem {
  search_type: string
  search_value: string
  result: ItemSearchResult | null
  searched_at: string
}
