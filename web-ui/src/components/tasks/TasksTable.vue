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
}

const props = defineProps<Props>()

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
  <div class="border rounded-lg bg-white overflow-x-auto">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead class="w-[80px]">启用</TableHead>
          <TableHead>任务名称</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>关键词</TableHead>
          <TableHead>价格范围</TableHead>
          <TableHead>筛选条件</TableHead>
          <TableHead>最大页数</TableHead>
          <TableHead>AI 标准</TableHead>
          <TableHead>定时规则</TableHead>
          <TableHead class="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <template v-if="isLoading && tasks.length === 0">
          <TableRow>
            <TableCell :colspan="10" class="h-24 text-center text-muted-foreground">
              正在加载中...
            </TableCell>
          </TableRow>
        </template>
        <template v-else-if="tasks.length === 0">
          <TableRow>
            <TableCell :colspan="10" class="h-24 text-center text-muted-foreground">
              没有找到任何任务。
            </TableCell>
          </TableRow>
        </template>
        <template v-else>
          <TableRow 
            v-for="task in tasks" 
            :key="task.id"
          >
            <TableCell>
              <Switch 
                :model-value="task.enabled" 
                @update:model-value="(val: boolean) => emit('toggle-enabled', task, val)" 
              />
            </TableCell>
            <TableCell class="font-medium">
              {{ task.task_name }}
            </TableCell>
            <TableCell>
              <Badge 
                :variant="task.is_running ? 'default' : 'secondary'"
                :class="task.is_running ? 'bg-green-500 hover:bg-green-600' : ''"
              >
                {{ task.is_running ? '运行中' : '已停止' }}
              </Badge>
            </TableCell>
            <TableCell>
              <code class="px-1.5 py-0.5 bg-gray-100 rounded text-sm">{{ task.keyword }}</code>
            </TableCell>
            <TableCell class="text-sm text-gray-500">
              {{ task.min_price || '不限' }} - {{ task.max_price || '不限' }}
            </TableCell>
            <TableCell>
              <div class="flex flex-wrap gap-2 items-center">
                <Badge v-if="task.personal_only" variant="secondary">
                  个人闲置
                </Badge>
                <Badge v-else variant="outline" class="text-gray-500">
                  个人/商家不限
                </Badge>
                <Badge v-if="task.free_shipping" variant="secondary">
                  包邮
                </Badge>
                <Badge v-else variant="outline" class="text-gray-500">
                  运费不限
                </Badge>
                <Badge variant="outline">
                  新发布：{{ task.new_publish_option || '不筛选' }}
                </Badge>
                <span class="text-xs text-gray-500 truncate max-w-[180px]" :title="task.region || '—'">
                  区域：{{ task.region || '—' }}
                </span>
              </div>
            </TableCell>
            <TableCell class="text-sm text-gray-500">
              {{ task.max_pages || 3 }}
            </TableCell>
            <TableCell class="text-sm text-gray-500">
              <div class="flex items-center gap-2">
                <code class="px-1.5 py-0.5 bg-gray-100 rounded text-xs">
                  {{ (task.ai_prompt_criteria_file || 'N/A').replace('prompts/', '') }}
                </code>
                <Button size="sm" variant="outline" @click="emit('refresh-criteria', task)">
                  重新生成
                </Button>
              </div>
            </TableCell>
            <TableCell class="text-sm text-gray-500">
              {{ task.cron || '手动触发' }}
            </TableCell>
            <TableCell class="text-right">
              <div class="flex justify-end items-center gap-2">
                <Button 
                  v-if="!task.is_running" 
                  size="sm" 
                  variant="default"
                  class="min-w-[80px]"
                  :class="task.enabled
                    ? 'bg-green-600 hover:bg-green-700 text-white'
                    : 'bg-gray-200 text-gray-500 hover:bg-gray-200'"
                  :disabled="!task.enabled"
                  @click="emit('run-task', task.id)"
                >
                  <Play class="w-3 h-3 mr-1 fill-current" /> 运行
                </Button>
                <Button 
                  v-else 
                  size="sm" 
                  variant="destructive"
                  class="min-w-[80px]"
                  @click="emit('stop-task', task.id)"
                >
                  <Square class="w-3 h-3 mr-1 fill-current" /> 停止
                </Button>

                <div class="w-px h-4 bg-gray-200 mx-1"></div>

                <Button size="icon" variant="ghost" title="编辑" @click="emit('edit-task', task)">
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
