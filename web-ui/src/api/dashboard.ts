import { http } from '@/lib/http'
import type { DashboardSnapshot } from '@/types/dashboard.d.ts'

export async function getDashboardSummary(): Promise<DashboardSnapshot> {
  return await http('/api/dashboard/summary')
}
