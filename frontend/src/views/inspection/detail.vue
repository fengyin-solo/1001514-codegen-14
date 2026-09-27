<template>
  <section class="page" data-module="inspection">
    <header class="page-head">
      <div>
        <h2>巡检单明细</h2>
        <p class="page-desc">查看单张巡检单的登记信息与当前状态。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回巡检任务列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <table v-if="entry" class="data-table detail-table">
      <tbody>
        <tr v-for="field in fields" :key="field">
          <th>{{ field }}</th>
          <td>{{ entry[field] ?? '—' }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span v-if="entry">巡检单号：{{ entry['巡检单号'] }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/inspection'
const fields = ["巡检单号", "巡检站点", "巡检人员", "巡检日期", "巡检项目", "发现问题数", "巡检时长", "巡检状态"]

const route = useRoute()
const router = useRouter()
const entry = ref<Row | null>(null)
const errorMessage = ref('')

function goBack() {
  // 回列表页：筛选范围存在 inspection store 里，列表页挂载时会按原口径恢复
  void router.push({ name: 'inspection' })
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}`)
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail ?? '巡检单明细读取失败')
    }
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检单明细读取失败'
  }
}

onMounted(load)
</script>
