<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <aside class="w-56 bg-white border-r border-gray-200 flex-shrink-0">
    <nav class="pt-6">
      <ul>
        <li>
          <RouterLink
            to="/tasks"
            class="block px-6 py-3 text-gray-700 border-r-4 border-transparent hover:bg-blue-50"
            active-class="!border-blue-500 !text-blue-600 !font-semibold bg-blue-50"
          >
            任务管理
          </RouterLink>
        </li>
        <li>
          <RouterLink
            to="/accounts"
            class="block px-6 py-3 text-gray-700 border-r-4 border-transparent hover:bg-blue-50"
            active-class="!border-blue-500 !text-blue-600 !font-semibold bg-blue-50"
          >
            账号管理
          </RouterLink>
        </li>
        <li>
          <RouterLink
            to="/results"
            class="block px-6 py-3 text-gray-700 border-r-4 border-transparent hover:bg-blue-50"
            active-class="!border-blue-500 !text-blue-600 !font-semibold bg-blue-50"
          >
            结果查看
          </RouterLink>
        </li>
        <li>
          <RouterLink
            to="/logs"
            class="block px-6 py-3 text-gray-700 border-r-4 border-transparent hover:bg-blue-50"
            active-class="!border-blue-500 !text-blue-600 !font-semibold bg-blue-50"
          >
            运行日志
          </RouterLink>
        </li>
        <li>
          <RouterLink
            to="/settings"
            class="block px-6 py-3 text-gray-700 border-r-4 border-transparent hover:bg-blue-50"
            active-class="!border-blue-500 !text-blue-600 !font-semibold bg-blue-50"
          >
            系统设置
          </RouterLink>
        </li>
      </ul>
    </nav>
  </aside>
</template>
