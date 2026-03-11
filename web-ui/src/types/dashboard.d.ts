import type { ResultInsights } from '@/types/result.d.ts'

export interface DashboardSummary {
  enabled_tasks: number
  running_tasks: number
  result_files: number
  scanned_items: number
  recommended_items: number
  ai_recommended_items: number
  keyword_recommended_items: number
  last_updated_at: string | null
}

export interface DashboardTaskSummary {
  task_id: number | null
  task_name: string
  keyword: string
  filename: string | null
  enabled: boolean
  is_running: boolean
  account_strategy: 'auto' | 'fixed' | 'rotate'
  cron: string | null
  region: string | null
  total_items: number
  recommended_items: number
  ai_recommended_items: number
  keyword_recommended_items: number
  latest_crawl_time: string | null
  latest_recommended_title: string | null
  latest_recommended_price: number | null
}

export interface DashboardActivity {
  id: string
  type: 'recommendation' | 'scan' | 'task'
  task_name: string
  keyword: string
  title: string
  status: string
  detail: string | null
  filename: string | null
  timestamp: string | null
}

export interface DashboardSnapshot {
  summary: DashboardSummary
  task_summaries: DashboardTaskSummary[]
  recent_activities: DashboardActivity[]
  focus_file: string | null
}

export interface DashboardSuggestion {
  title: string
  description: string
  actionLabel: string
  routeName: 'Tasks' | 'Settings'
  query: Record<string, string>
}

export interface DashboardState {
  snapshot: DashboardSnapshot | null
  focusInsights: ResultInsights | null
}
