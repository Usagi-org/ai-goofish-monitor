<script setup lang="ts">
import { ref } from 'vue'
import type { ResultItem } from '@/types/result.d.ts'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

interface Props {
  item: ResultItem
}

const props = defineProps<Props>()

const info = props.item.商品信息
const seller = props.item.卖家信息
const ai = props.item.ai_analysis

const isRecommended = ai?.is_recommended === true
const recommendationText = isRecommended ? '推荐' : (ai?.is_recommended === false ? '不推荐' : '待定')

const imageUrl = info.商品图片列表?.[0] || info.商品主图链接 || ''
const crawlTime = props.item.爬取时间
  ? new Date(props.item.爬取时间).toLocaleString('sv-SE')
  : '未知'
const publishTime = info.发布时间 || '未知'

const expanded = ref(false)
</script>

<template>
  <Card class="flex flex-col h-full">
    <CardHeader>
      <div class="aspect-[4/3] bg-gray-100 rounded-t-lg overflow-hidden -mt-6 -mx-6">
        <a :href="info.商品链接" target="_blank" rel="noopener noreferrer">
          <img
            :src="imageUrl"
            :alt="info.商品标题"
            class="w-full h-full object-cover transition-transform hover:scale-105"
            loading="lazy"
          />
        </a>
      </div>
      <CardTitle class="pt-4">
        <a :href="info.商品链接" target="_blank" rel="noopener noreferrer" class="hover:text-blue-600 line-clamp-2">
          {{ info.商品标题 }}
        </a>
      </CardTitle>
      <CardDescription class="text-xl font-bold text-red-600 !mt-2">
        {{ info.当前售价 }}
      </CardDescription>
    </CardHeader>
    <CardContent class="flex-grow">
      <div
        :class="[
          'p-3 rounded-md text-sm',
          isRecommended ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
        ]"
      >
        <p class="font-semibold" :class="[isRecommended ? 'text-green-800' : 'text-red-800']">
          AI建议: {{ recommendationText }}
        </p>
        <p class="mt-1 text-gray-600" :class="{ 'line-clamp-3': !expanded }">
          原因: {{ ai?.reason || '无' }}
        </p>
        <button
          v-if="ai?.reason"
          @click="expanded = !expanded"
          class="mt-1 text-xs text-blue-600 hover:underline"
        >
          {{ expanded ? '收起' : '展开' }}
        </button>
      </div>
    </CardContent>
    <CardFooter class="text-xs text-gray-500 flex items-center justify-between gap-2">
      <div class="space-y-1">
        <span class="block">卖家: {{ seller.卖家昵称 || info.卖家昵称 || '未知' }}</span>
        <span class="block">发布于: {{ publishTime }}</span>
        <span class="block">抓取于: {{ crawlTime }}</span>
      </div>
      <a
        :href="info.商品链接"
        target="_blank"
        rel="noopener noreferrer"
        class="text-blue-600 hover:underline text-sm"
      >
        查看详情
      </a>
    </CardFooter>
  </Card>
</template>
