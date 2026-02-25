<script setup lang="ts">
import { computed, ref } from 'vue'
import { useResults } from '@/composables/useResults'
import ResultsFilterBar from '@/components/results/ResultsFilterBar.vue'
import ResultsGrid from '@/components/results/ResultsGrid.vue'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const {
  files,
  selectedFile,
  results,
  filters,
  isLoading,
  error,
  refreshResults,
  deleteSelectedFile,
  fileOptions,
  isFileOptionsReady,
} = useResults()

const isDeleteDialogOpen = ref(false)

const selectedTaskLabel = computed(() => {
  if (!selectedFile.value || fileOptions.value.length === 0) return null
  const match = fileOptions.value.find((option) => option.value === selectedFile.value)
  if (!match) return null
  const label = match.label.replace(/^任务名称：/, '').trim()
  return label || null
})

const deleteConfirmText = computed(() => {
  return selectedTaskLabel.value
    ? `确定删除任务结果「${selectedTaskLabel.value}」吗？此操作不可恢复。`
    : '确定删除该任务结果吗？此操作不可恢复。'
})

function openDeleteDialog() {
  if (!selectedFile.value) {
    toast({
      title: '暂无可删除的结果',
      variant: 'destructive',
    })
    return
  }
  isDeleteDialogOpen.value = true
}

async function handleDeleteResults() {
  if (!selectedFile.value) return
  try {
    await deleteSelectedFile(selectedFile.value)
    toast({ title: '结果已删除' })
  } catch (e) {
    toast({
      title: '删除结果失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isDeleteDialogOpen.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-800 mb-6">
      结果查看
    </h1>

    <div v-if="error" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
      <strong class="font-bold">出错了!</strong>
      <span class="block sm:inline">{{ error.message }}</span>
    </div>

    <ResultsFilterBar
      :files="files"
      :file-options="fileOptions"
      :is-ready="isFileOptionsReady"
      v-model:selectedFile="selectedFile"
      v-model:aiRecommendedOnly="filters.ai_recommended_only"
      v-model:keywordRecommendedOnly="filters.keyword_recommended_only"
      v-model:sortBy="filters.sort_by"
      v-model:sortOrder="filters.sort_order"
      :is-loading="isLoading"
      @refresh="refreshResults"
      @delete="openDeleteDialog"
    />

    <ResultsGrid :results="results" :is-loading="isLoading" />

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>删除任务结果</DialogTitle>
          <DialogDescription>
            {{ deleteConfirmText }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteDialogOpen = false">取消</Button>
          <Button variant="destructive" :disabled="isLoading" @click="handleDeleteResults">
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
