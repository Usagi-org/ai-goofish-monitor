<script setup lang="ts">
import type { Task } from '@/types/task.d.ts'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Play, Square, Pencil, Trash2 } from 'lucide-vue-next'

interface Props {
  tasks: Task[]
  isLoading: boolean
  stoppingIds?: Set<number>
}

const props = defineProps<Props>()
const isStopping = (id: number) => props.stoppingIds?.has(id) ?? false

const emit = defineEmits<{
  (e: 'delete-task', taskId: number): void
  (e: 'run-task', taskId: number): void
  (e: 'stop-task', taskId: number): void
  (e: 'edit-task', task: Task): void
  (e: 'refresh-criteria', task: Task): void
  (e: 'toggle-enabled', task: Task, enabled: boolean): void
}>()
</script>

<template>
  <div class="border rounded-xl bg-slate-50/80 shadow-sm overflow-x-auto">
    <Table class="min-w-full">
      <TableHeader class="bg-white/70 backdrop-blur">
        <TableRow class="border-b">
          <TableHead class="w-[84px] text-center text-slate-600">启用</TableHead>
          <TableHead class="text-slate-600">任务</TableHead>
          <TableHead class="text-center text-slate-600">状态</TableHead>
          <TableHead class="text-center text-slate-600">价格范围</TableHead>
          <TableHead class="text-center text-slate-600">筛选条件</TableHead>
          <TableHead class="text-center text-slate-600">最大页数</TableHead>
          <TableHead class="text-center text-slate-600">AI 标准</TableHead>
          <TableHead class="text-center text-slate-600">定时规则</TableHead>
          <TableHead class="text-right text-slate-600">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <template v-if="isLoading && tasks.length === 0">
          <TableRow>
            <TableCell :colspan="9" class="h-24 text-center text-muted-foreground">
              正在加载中...
            </TableCell>
          </TableRow>
        </template>
        <template v-else-if="tasks.length === 0">
          <TableRow>
            <TableCell :colspan="9" class="h-24 text-center text-muted-foreground">
              没有找到任何任务。
            </TableCell>
          </TableRow>
        </template>
        <template v-else>
          <TableRow
            v-for="task in tasks"
            :key="task.id"
            class="hover:bg-white transition-colors border-b last:border-b-0"
          >
            <TableCell class="text-center align-middle">
              <Switch
                :model-value="task.enabled"
                @update:model-value="(val: boolean) => emit('toggle-enabled', task, val)"
              />
            </TableCell>

            <TableCell class="align-middle">
              <div class="flex flex-col gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-base font-semibold text-slate-900">{{ task.task_name }}</span>
                  <Badge variant="outline" class="border-slate-200 text-xs text-slate-500">
                    关键词
                  </Badge>
                  <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-mono text-slate-700">
                    {{ task.keyword }}
                  </span>
                </div>
                <div class="text-xs text-slate-500" v-if="task.description">
                  {{ task.description }}
                </div>
              </div>
            </TableCell>

            <TableCell class="text-center align-middle">
              <Badge
                :variant="task.is_running ? 'default' : 'secondary'"
                :class="
                  task.is_running
                    ? 'bg-emerald-100 text-emerald-700 border-0 hover:bg-emerald-100'
                    : 'bg-amber-100 text-amber-700 border-0'
                "
              >
                {{ task.is_running ? '运行中' : '已停止' }}
              </Badge>
              <div class="mt-2 text-xs text-slate-500">
                {{ task.enabled ? '已启用' : '未启用' }}
              </div>
            </TableCell>

            <TableCell class="text-center align-middle">
              <div class="inline-flex flex-col items-center gap-1">
                <span class="text-sm font-semibold text-slate-800">
                  {{ task.min_price || '不限' }} - {{ task.max_price || '不限' }}
                </span>
                <span class="text-xs text-slate-500">价格范围 (元)</span>
              </div>
            </TableCell>

            <TableCell class="align-middle">
              <div class="flex flex-col items-center gap-2 text-xs text-slate-600">
                <div class="flex flex-wrap justify-center gap-2">
                  <Badge v-if="task.personal_only" variant="secondary" class="bg-slate-100 text-slate-700 border-0">
                    个人闲置
                  </Badge>
                  <Badge v-else variant="outline" class="border-slate-200 text-slate-500">
                    个人/商家不限
                  </Badge>
                  <Badge v-if="task.free_shipping" variant="secondary" class="bg-slate-100 text-slate-700 border-0">
                    包邮
                  </Badge>
                  <Badge v-else variant="outline" class="border-slate-200 text-slate-500">
                    运费不限
                  </Badge>
                </div>
                <div class="flex flex-wrap justify-center gap-2">
                  <Badge variant="outline" class="border-slate-200 text-slate-600 bg-white">
                    新发布：{{ task.new_publish_option || '不筛选' }}
                  </Badge>
                  <span class="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600" :title="task.region || '—'">
                    区域：{{ task.region || '—' }}
                  </span>
                </div>
              </div>
            </TableCell>

            <TableCell class="text-center align-middle">
              <div class="inline-flex items-center justify-center w-12 h-10 rounded-md bg-slate-100 text-base font-semibold text-slate-700">
                {{ task.max_pages || 3 }}
              </div>
            </TableCell>

            <TableCell class="align-middle">
              <div class="flex flex-col items-center gap-2">
                <span
                  class="px-2 py-1 rounded-md bg-slate-100 text-xs font-mono text-slate-700 truncate max-w-[170px]"
                  :title="task.ai_prompt_criteria_file || '暂无标准文件'"
                >
                  {{ (task.ai_prompt_criteria_file || 'N/A').replace('prompts/', '') }}
                </span>
                <Button size="sm" variant="outline" class="h-8" @click="emit('refresh-criteria', task)">
                  重新生成
                </Button>
              </div>
            </TableCell>

            <TableCell class="text-center align-middle">
              <div class="flex flex-col items-center gap-1">
                <span class="text-sm font-medium text-slate-800">
                  {{ task.cron || '手动触发' }}
                </span>
                <span class="text-xs text-slate-500">定时规则</span>
              </div>
            </TableCell>

            <TableCell class="text-right align-middle">
              <div class="flex justify-end items-center gap-2">
                <Button
                  v-if="!task.is_running"
                  size="sm"
                  variant="default"
                  class="min-w-[86px] shadow-sm"
                  :class="task.enabled
                    ? 'bg-emerald-500 hover:bg-emerald-600 text-white'
                    : 'bg-slate-200 text-slate-500 hover:bg-slate-200'"
                  :disabled="!task.enabled"
                  @click="emit('run-task', task.id)"
                >
                  <Play class="w-3 h-3 mr-1 fill-current" /> 运行
                </Button>
                <Button
                  v-else
                  size="sm"
                  variant="destructive"
                  class="min-w-[86px]"
                  :disabled="isStopping(task.id)"
                  @click="emit('stop-task', task.id)"
                >
                  <template v-if="isStopping(task.id)">
                    停止中...
                  </template>
                  <template v-else>
                    <Square class="w-3 h-3 mr-1 fill-current" /> 停止
                  </template>
                </Button>

                <div class="w-px h-4 bg-slate-200 mx-1"></div>

                <Button size="icon" variant="ghost" title="编辑" class="hover:bg-blue-50" @click="emit('edit-task', task)">
                  <Pencil class="w-4 h-4 text-blue-600" />
                </Button>

                <Button size="icon" variant="ghost" title="删除" class="text-red-500 hover:text-red-700 hover:bg-red-50" @click="emit('delete-task', task.id)">
                  <Trash2 class="w-4 h-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </template>
      </TableBody>
    </Table>
  </div>
</template>
