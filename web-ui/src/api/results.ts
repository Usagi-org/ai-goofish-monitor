import type {
  CheckItemStatusEntry,
  CheckItemStatusResponse,
  ItemStatus,
  ResultInsights,
  ResultItem,
} from '@/types/result.d.ts'
import { http } from '@/lib/http'

export type { CheckItemStatusEntry, CheckItemStatusResponse, ItemStatus }

export interface GetResultContentParams {
  recommended_only?: boolean;
  ai_recommended_only?: boolean;
  keyword_recommended_only?: boolean;
  include_hidden?: boolean;
  include_sold?: boolean;
  sort_by?: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count';
  sort_order?: 'asc' | 'desc';
  page?: number;
  limit?: number;
}

export interface CheckItemStatusParams {
  item_ids?: string[];
  limit?: number;
}

export async function getResultFiles(): Promise<string[]> {
  const data = await http('/api/results/files')
  return data.files || []
}

export async function deleteResultFile(filename: string): Promise<{ message: string }> {
  return await http(`/api/results/files/${encodeURIComponent(filename)}`, { method: 'DELETE' })
}

export async function getResultContent(
  filename: string,
  params: GetResultContentParams = {}
): Promise<{ total_items: number; items: ResultItem[] }> {
  return await http(`/api/results/${encodeURIComponent(filename)}`, { params: params as Record<string, any> })
}

export async function getResultInsights(filename: string): Promise<ResultInsights> {
  return await http(`/api/results/${encodeURIComponent(filename)}/insights`)
}

export async function getResultBlacklistRules(filename: string): Promise<{ keywords: string[] }> {
  return await http(`/api/results/${encodeURIComponent(filename)}/blacklist-rules`)
}

export async function updateResultBlacklistRules(filename: string, keywords: string[]): Promise<{ message: string; keywords: string[] }> {
  return await http(`/api/results/${encodeURIComponent(filename)}/blacklist-rules`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keywords }),
  })
}

export function buildResultExportUrl(filename: string, params: GetResultContentParams = {}): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.set(key, String(value))
    }
  })
  const queryString = searchParams.toString()
  return `/api/results/${encodeURIComponent(filename)}/export${queryString ? `?${queryString}` : ''}`
}

export function downloadResultExport(filename: string, params: GetResultContentParams = {}) {
  const url = buildResultExportUrl(filename, params)
  const link = document.createElement('a')
  link.href = url
  link.download = ''
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export async function updateItemStatus(
  filename: string,
  itemId: string,
  status: ItemStatus
): Promise<{ message: string; status: ItemStatus }> {
  return await http(`/api/results/${encodeURIComponent(filename)}/items/${encodeURIComponent(itemId)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export async function checkResultStatus(
  filename: string,
  payload: CheckItemStatusParams = {}
): Promise<CheckItemStatusResponse> {
  return await http(`/api/results/${encodeURIComponent(filename)}/check-status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
