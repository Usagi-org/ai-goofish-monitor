<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import type { Task, TaskGenerateRequest } from '@/types/task.d.ts'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type FormMode = 'create' | 'edit'
type EmittedData = TaskGenerateRequest | Partial<Task>

const props = defineProps<{
  mode: FormMode
  initialData?: Task | null
  accountOptions?: { name: string; path: string }[]
  defaultAccount?: string
}>()

const emit = defineEmits<{
  (e: 'submit', data: EmittedData): void
}>()

const form = ref<EmittedData>({})

// Initialize form based on mode and initialData
watchEffect(() => {
  if (props.mode === 'edit' && props.initialData) {
    form.value = {
      ...props.initialData,
      account_state_file: props.initialData.account_state_file || '',
    }
  } else {
    form.value = {
      task_name: '',
      keyword: '',
      description: '',
      max_pages: 3,
      personal_only: true,
      min_price: undefined,
      max_price: undefined,
      cron: '',
      account_state_file: props.defaultAccount || '',
    }
  }
})

function handleSubmit() {
  // Basic validation
  if (!form.value.task_name || !form.value.keyword || !form.value.description) {
    toast({
      title: '信息不完整',
      description: '任务名称、关键词和详细需求不能为空。',
      variant: 'destructive',
    })
    return
  }

  // Filter out fields that shouldn't be sent in update requests
  const { id, is_running, ...submitData } = form.value as any
  if (submitData.account_state_file === '') {
    submitData.account_state_file = null
  }
  emit('submit', submitData)
}
</script>

<template>
  <form id="task-form" @submit.prevent="handleSubmit">
    <div class="grid gap-6 py-4">
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="task-name" class="text-right">任务名称</Label>
        <Input id="task-name" v-model="form.task_name" class="col-span-3" placeholder="例如：索尼 A7M4 相机" required />
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="keyword" class="text-right">搜索关键词</Label>
        <Input id="keyword" v-model="form.keyword" class="col-span-3" placeholder="例如：a7m4" required />
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="description" class="text-right">详细需求</Label>
        <Textarea
          id="description"
          v-model="form.description"
          class="col-span-3"
          placeholder="请用自然语言详细描述你的购买需求，AI将根据此描述生成分析标准..."
          required
        />
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label class="text-right">价格范围</Label>
        <div class="col-span-3 flex items-center gap-2">
          <Input type="number" v-model="form.min_price as any" placeholder="最低价" />
          <span>-</span>
          <Input type="number" v-model="form.max_price as any" placeholder="最高价" />
        </div>
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="max-pages" class="text-right">搜索页数</Label>
        <Input id="max-pages" v-model.number="form.max_pages" type="number" class="col-span-3" />
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="cron" class="text-right">定时规则</Label>
        <Input id="cron" v-model="form.cron as any" class="col-span-3" placeholder="分 时 日 月 周 (例如: 0 8 * * *)" />
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label class="text-right">绑定账号</Label>
        <div class="col-span-3">
          <Select v-model="form.account_state_file">
            <SelectTrigger>
              <SelectValue placeholder="未绑定（自动选择）" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">未绑定（自动选择）</SelectItem>
              <SelectItem v-for="account in accountOptions || []" :key="account.path" :value="account.path">
                {{ account.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="personal-only" class="text-right">仅个人卖家</Label>
        <Switch id="personal-only" v-model="form.personal_only" />
      </div>
    </div>
  </form>
</template>
