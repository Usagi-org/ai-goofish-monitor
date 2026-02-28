import type { ResultItem } from '@/types/result.d.ts'
import { http } from '@/lib/http'

export interface GetResultContentParams {
  recommended_only?: boolean;
  ai_recommended_only?: boolean;
  keyword_recommended_only?: boolean;
  sort_by?: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count';
  sort_order?: 'asc' | 'desc';
  page?: number;
  limit?: number;
}

export async function getResultFiles(): Promise<string[]> {
  const data = await http('/api/results/files')
  return data.files || []
}

export async function deleteResultFile(filename: string): Promise<{ message: string }> {
  return await http(`/api/results/files/${filename}`, { method: 'DELETE' })
}

export async function getResultContent(
  filename: string,
  params: GetResultContentParams = {}
): Promise<{ total_items: number; items: ResultItem[] }> {
  return await http(`/api/results/${filename}`, { params: params as Record<string, any> })
}
