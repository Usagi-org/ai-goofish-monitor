<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import type { KeywordRuleGroup, Task, TaskGenerateRequest } from '@/types/task.d.ts'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type FormMode = 'create' | 'edit'
type EmittedData = TaskGenerateRequest | Partial<Task>

interface KeywordRuleGroupForm {
  name: string
  includeInput: string
  excludeInput: string
}

const props = defineProps<{
  mode: FormMode
  initialData?: Task | null
  accountOptions?: { name: string; path: string }[]
  defaultAccount?: string
}>()

const emit = defineEmits<{
  (e: 'submit', data: EmittedData): void
}>()

const form = ref<any>({})
const keywordRuleGroups = ref<KeywordRuleGroupForm[]>([])

function parseKeywordText(text: string): string[] {
  const values = String(text || '')
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)

  const seen = new Set<string>()
  const deduped: string[] = []
  for (const value of values) {
    const key = value.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(value)
  }
  return deduped
}

function toGroupForm(group?: KeywordRuleGroup | null): KeywordRuleGroupForm {
  if (!group) {
    return {
      name: '',
      includeInput: '',
      excludeInput: '',
    }
  }
  return {
    name: group.name || '',
    includeInput: (group.include_keywords || []).join('\n'),
    excludeInput: (group.exclude_keywords || []).join('\n'),
  }
}

function addKeywordGroup() {
  keywordRuleGroups.value.push(toGroupForm())
}

function removeKeywordGroup(index: number) {
  keywordRuleGroups.value.splice(index, 1)
}

function buildKeywordRuleGroups(): KeywordRuleGroup[] {
  return keywordRuleGroups.value
    .map((group) => {
      const includeKeywords = parseKeywordText(group.includeInput)
      const excludeKeywords = parseKeywordText(group.excludeInput)
      return {
        name: group.name.trim() || null,
        include_keywords: includeKeywords,
        exclude_keywords: excludeKeywords,
      } as KeywordRuleGroup
    })
    .filter((group) => group.include_keywords.length > 0)
}

// Initialize form based on mode and initialData
watchEffect(() => {
  if (props.mode === 'edit' && props.initialData) {
    form.value = {
      ...props.initialData,
      account_state_file: props.initialData.account_state_file || '',
      free_shipping: props.initialData.free_shipping ?? true,
      new_publish_option: props.initialData.new_publish_option || '__none__',
      region: props.initialData.region || '',
      decision_mode: props.initialData.decision_mode || 'ai',
    }

    const existingGroups = props.initialData.keyword_rule_groups || []
    keywordRuleGroups.value = existingGroups.map((group) => toGroupForm(group))
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
      free_shipping: true,
      new_publish_option: '__none__',
      region: '',
      decision_mode: 'ai',
    }
    keywordRuleGroups.value = []
  }
})

watchEffect(() => {
  if (form.value.decision_mode === 'keyword' && keywordRuleGroups.value.length === 0) {
    addKeywordGroup()
  }
})

function handleSubmit() {
  if (!form.value.task_name || !form.value.keyword) {
    toast({
      title: '信息不完整',
      description: '任务名称和关键词不能为空。',
      variant: 'destructive',
    })
    return
  }

  const decisionMode = form.value.decision_mode || 'ai'
  if (decisionMode === 'ai' && !String(form.value.description || '').trim()) {
    toast({
      title: '信息不完整',
      description: 'AI 模式下详细需求不能为空。',
      variant: 'destructive',
    })
    return
  }

  const normalizedGroups = buildKeywordRuleGroups()
  if (decisionMode === 'keyword' && normalizedGroups.length === 0) {
    toast({
      title: '关键词规则不完整',
      description: '关键词模式下至少需要一个分组，且每个分组至少有一个包含关键词。',
      variant: 'destructive',
    })
    return
  }

  // Filter out fields that shouldn't be sent in update requests
  const { id, is_running, ...submitData } = form.value as any

  if (submitData.account_state_file === '') {
    submitData.account_state_file = null
  }

  if (typeof submitData.region === 'string') {
    const normalized = submitData.region
      .trim()
      .split('/')
      .map((part: string) => part.trim().replace(/(省|市)$/u, ''))
      .filter((part: string) => part.length > 0)
      .join('/')
    submitData.region = normalized
  }

  if (submitData.new_publish_option === '__none__') {
    submitData.new_publish_option = ''
  }

  submitData.decision_mode = decisionMode
  submitData.keyword_rule_groups = decisionMode === 'keyword' ? normalizedGroups : []
  if (decisionMode === 'keyword' && !submitData.description) {
    submitData.description = ''
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
        <Label class="text-right">判断模式</Label>
        <div class="col-span-3">
          <Select v-model="form.decision_mode">
            <SelectTrigger>
              <SelectValue placeholder="请选择判断模式" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ai">AI判断</SelectItem>
              <SelectItem value="keyword">关键词判断</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="description" class="text-right">详细需求</Label>
        <div class="col-span-3 space-y-1">
          <Textarea
            id="description"
            v-model="form.description"
            placeholder="请用自然语言详细描述你的购买需求，AI将根据此描述生成分析标准..."
          />
          <p v-if="form.decision_mode === 'keyword'" class="text-xs text-gray-500">
            关键词模式下可留空；AI模式下必填。
          </p>
        </div>
      </div>

      <div v-if="form.decision_mode === 'keyword'" class="grid grid-cols-4 gap-4">
        <Label class="text-right pt-2">关键词规则</Label>
        <div class="col-span-3 space-y-3">
          <p class="text-xs text-gray-500">
            规则逻辑：组内“包含词”是 AND，组内“排除词”是 NOT，组间是 OR。
          </p>
          <div
            v-for="(group, index) in keywordRuleGroups"
            :key="`group-${index}`"
            class="rounded-md border border-slate-200 p-3 space-y-2"
          >
            <div class="flex items-center justify-between gap-2">
              <Input
                v-model="group.name"
                :placeholder="`规则组名称（可选）- 组 ${index + 1}`"
                class="flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                @click="removeKeywordGroup(index)"
                :disabled="keywordRuleGroups.length === 1"
              >
                删除组
              </Button>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="space-y-1">
                <Label class="text-xs">包含关键词（AND）</Label>
                <Textarea
                  v-model="group.includeInput"
                  class="min-h-[90px]"
                  placeholder="每行一个关键词，或使用逗号分隔"
                />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">排除关键词（NOT）</Label>
                <Textarea
                  v-model="group.excludeInput"
                  class="min-h-[90px]"
                  placeholder="每行一个关键词，或使用逗号分隔"
                />
              </div>
            </div>
          </div>
          <Button type="button" variant="outline" size="sm" @click="addKeywordGroup">
            + 添加规则组
          </Button>
        </div>
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
      <div class="grid grid-cols-4 items-center gap-4">
        <Label class="text-right">是否包邮</Label>
        <Switch v-model="form.free_shipping" />
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label class="text-right">新发布范围</Label>
        <div class="col-span-3">
          <Select v-model="form.new_publish_option as any">
            <SelectTrigger>
              <SelectValue placeholder="不筛选（默认）" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">不筛选（默认）</SelectItem>
              <SelectItem value="最新">最新</SelectItem>
              <SelectItem value="1天内">1天内</SelectItem>
              <SelectItem value="3天内">3天内</SelectItem>
              <SelectItem value="7天内">7天内</SelectItem>
              <SelectItem value="14天内">14天内</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label class="text-right">区域筛选(默认不填)</Label>
        <div class="col-span-3 space-y-1">
          <Input
            v-model="form.region as any"
            placeholder="例如： 浙江/杭州/滨江区 或 浙江/杭州/全杭州 或 上海/徐汇区"
          />
          <p class="text-xs text-gray-500">区域筛选会导致满足条件的商品数量很少</p>
        </div>
      </div>
    </div>
  </form>
</template>
