import { http } from '@/lib/http'
import type {
  SellerInfo,
  SellerListResponse,
  ItemSearchResult,
  SearchHistoryItem,
  MetricsSnapshot,
  PriceHistoryPoint,
  WantCountHistoryPoint,
} from '@/types/seller.d.ts'

// ===== 卖家管理 =====

export async function getSellerInfo(sellerId: string): Promise<SellerInfo> {
  return await http(`/api/sellers/${sellerId}`)
}

export async function addToBlacklist(sellerId: string, reason: string = ''): Promise<void> {
  await http('/api/sellers/blacklist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seller_id: sellerId, reason }),
  })
}

export async function addToWhitelist(sellerId: string, reason: string = ''): Promise<void> {
  await http('/api/sellers/whitelist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seller_id: sellerId, reason }),
  })
}

export async function removeFromList(sellerId: string): Promise<void> {
  await http(`/api/sellers/list/${sellerId}`, { method: 'DELETE' })
}

export async function getBlacklist(): Promise<SellerListResponse[]> {
  return await http('/api/sellers/blacklist/list')
}

export async function getWhitelist(): Promise<SellerListResponse[]> {
  return await http('/api/sellers/whitelist/list')
}

// ===== 商品 ID 搜索 =====

export async function searchByItemId(itemId: string): Promise<ItemSearchResult> {
  const result = await http('/api/sellers/search/item-id', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_id: itemId }),
  })
  return result.data
}

export async function getSearchHistory(limit: number = 20): Promise<SearchHistoryItem[]> {
  const result = await http(`/api/sellers/search-history?limit=${limit}`)
  return result.history
}

// ===== 指标历史 =====

export async function getPriceHistory(
  itemId: string,
  days: number = 30
): Promise<PriceHistoryPoint[]> {
  const result = await http(`/api/metrics/item/${itemId}/price-history?days=${days}`)
  return result.history
}

export async function getWantCountHistory(
  itemId: string,
  days: number = 30
): Promise<WantCountHistoryPoint[]> {
  const result = await http(`/api/metrics/item/${itemId}/want-history?days=${days}`)
  return result.history
}

export async function getLatestSnapshot(itemId: string): Promise<MetricsSnapshot> {
  const result = await http(`/api/metrics/item/${itemId}/latest`)
  return result.snapshot
}
