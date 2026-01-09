import { http } from '@/lib/http'

export async function getLogs(fromPos: number = 0, taskId?: number | null): Promise<{ new_content: string; new_pos: number }> {
  const params: Record<string, number> = { from_pos: fromPos }
  if (taskId !== null && taskId !== undefined) {
    params.task_id = taskId
  }
  return await http('/api/logs', { params })
}

export async function clearLogs(taskId?: number | null): Promise<void> {
  const params: Record<string, number> = {}
  if (taskId !== null && taskId !== undefined) {
    params.task_id = taskId
  }
  await http('/api/logs', { method: 'DELETE', params })
}

export async function getLogTail(
  taskId: number,
  offsetLines: number = 0,
  limitLines: number = 50
): Promise<{ content: string; has_more: boolean; next_offset: number; new_pos: number }> {
  return await http('/api/logs/tail', {
    params: {
      task_id: taskId,
      offset_lines: offsetLines,
      limit_lines: limitLines,
    },
  })
}
