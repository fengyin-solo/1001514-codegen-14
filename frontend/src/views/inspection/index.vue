<template>
  <section class="page" data-module="inspection">
    <header class="page-head">
      <div>
        <h2>巡检任务管理</h2>
        <p class="page-desc">维护巡检单，围绕巡检单号、巡检站点、巡检人员、巡检日期做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记巡检单</button>
        <button class="btn" type="button" @click="exportRows">导出巡检任务清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <section class="panel">
      <header class="panel-head">
        <div>
          <h3 class="panel-title">巡检问题分布</h3>
          <p class="panel-desc">按巡检单号与巡检人员汇总发现问题数（统计月份：{{ distMonth }}）</p>
        </div>
        <label class="filter-item">
          <span>站点范围</span>
          <select v-model="stationScope" @change="onStationScopeChange">
            <option value="">全部站点</option>
            <option v-for="station in distStations" :key="station" :value="station">{{ station }}</option>
          </select>
        </label>
      </header>

      <p v-if="distEmptyReason" class="empty-state dist-empty">{{ distEmptyReason }}</p>
      <div v-else class="dist-grid">
        <div class="dist-block">
          <h4 class="dist-title">按站点分布</h4>
          <div v-for="item in byStation" :key="item.station" class="dist-row">
            <span class="dist-name">{{ item.station }}</span>
            <span class="dist-bar"><i :style="{ width: barWidth(item.problem_count) }" /></span>
            <span class="dist-num">{{ item.problem_count }} 个问题 · {{ item.entry_count }} 单</span>
          </div>
        </div>
        <div class="dist-block">
          <h4 class="dist-title">按人员分布（点开查看名下巡检单）</h4>
          <div
            v-for="item in byPerson"
            :key="item.person"
            class="dist-row clickable"
            :class="{ active: activePerson === item.person }"
            @click="togglePerson(item.person)"
          >
            <span class="dist-name">{{ item.person }}</span>
            <span class="dist-bar"><i :style="{ width: barWidth(item.problem_count) }" /></span>
            <span class="dist-num">{{ item.problem_count }} 个问题 · {{ item.entry_count }} 单</span>
          </div>
        </div>
      </div>

      <div v-if="activePerson" class="person-entries">
        <h4 class="dist-title">{{ activePerson }} 名下的巡检单</h4>
        <table class="data-table">
          <thead>
            <tr>
              <th>巡检单号</th>
              <th>巡检站点</th>
              <th>巡检日期</th>
              <th>发现问题数</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in activePersonEntries" :key="entry.id">
              <td>{{ entry['巡检单号'] }}</td>
              <td>{{ entry['巡检站点'] }}</td>
              <td>{{ entry['巡检日期'] ?? '—' }}</td>
              <td>{{ entry['发现问题数'] }}</td>
              <td><button class="link" type="button" @click="openDetail(entry.id)">查看明细</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="excluded.length" class="dist-note">
        以下 {{ excluded.length }} 条记录未计入分布：
        <span v-for="item in excluded" :key="item.id" class="dist-excluded">
          {{ item['巡检单号'] }}（{{ item.reason }}）
        </span>
      </p>
    </section>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(Number(row.id))">详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无巡检任务数据，可先登记巡检单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条巡检任务记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useInspectionStore } from '@/stores/inspection'

type Row = Record<string, string | number | null>
type DistEntry = {
  id: number
  巡检单号: string
  巡检站点: string
  巡检人员: string
  巡检日期: string | null
  发现问题数: number
}
type DistRollup = { problem_count: number; entry_count: number }
type DistStation = DistRollup & { station: string }
type DistPerson = DistRollup & { person: string }
type DistExcluded = { id: number; 巡检单号: string; missing: string[]; reason: string }
type DistResponse = {
  month: string
  station: string
  stations: string[]
  month_total: number
  by_station: DistStation[]
  by_person: DistPerson[]
  entries: DistEntry[]
  excluded: DistExcluded[]
  empty_reason: string | null
}

const ENDPOINT = '/api/inspection'
const columns = ["巡检单号", "巡检站点", "巡检人员", "巡检日期", "巡检项目", "发现问题数", "巡检时长", "巡检状态"]
const actions = ["派发巡检", "提交结果", "作废巡检"]
// 列表筛选框是中文标签，提交时映射成接口参数
const FILTER_PARAM_MAP: Record<string, string> = { 巡检单号: 'keyword', 巡检站点: 'station', 巡检人员: 'person' }

const router = useRouter()
const store = useInspectionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ ...store.filters })
const filterFields = columns.slice(0, 3)

const stats = ref([
  { label: '本月发现问题', value: 0 },
  { label: '纳入分布巡检单', value: 0 },
  { label: '未计入记录', value: 0 },
])

const stationScope = ref(store.station)
const distMonth = ref('')
const distStations = ref<string[]>([])
const byStation = ref<DistStation[]>([])
const byPerson = ref<DistPerson[]>([])
const distEntries = ref<DistEntry[]>([])
const excluded = ref<DistExcluded[]>([])
const distEmptyReason = ref('')
const activePerson = ref('')

const activePersonEntries = computed(() =>
  distEntries.value.filter((entry) => entry['巡检人员'] === activePerson.value),
)
const maxProblemCount = computed(() =>
  Math.max(
    1,
    ...byStation.value.map((item) => item.problem_count),
    ...byPerson.value.map((item) => item.problem_count),
  ),
)

function barWidth(count: number) {
  return `${Math.max(4, Math.round((count / maxProblemCount.value) * 100))}%`
}

function togglePerson(person: string) {
  activePerson.value = activePerson.value === person ? '' : person
}

function openDetail(id: number) {
  // 进详情前把当前筛选口径留档，返回时列表与分布视图按同一口径恢复
  store.setFilters(filters.value)
  store.setStation(stationScope.value)
  void router.push({ name: 'inspection-detail', params: { id } })
}

function applyFilters() {
  store.setFilters(filters.value)
  void reload()
}

function resetFilters() {
  filters.value = {}
  store.setFilters({})
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '巡检单登记入口尚未接入审批流'
}

function onStationScopeChange() {
  store.setStation(stationScope.value)
  activePerson.value = ''
  void loadDistribution()
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('巡检任务动作未生效，请稍后重试')
    }
    await Promise.all([reload(), loadDistribution()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检任务操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const [label, value] of Object.entries(filters.value)) {
    const key = FILTER_PARAM_MAP[label]
    if (key && value) {
      params.set(key, value)
    }
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('巡检单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检任务列表读取失败'
  }
}

async function loadDistribution() {
  const params = new URLSearchParams()
  if (stationScope.value) {
    params.set('station', stationScope.value)
  }
  try {
    const response = await request(`${ENDPOINT}/distribution?${params.toString()}`)
    if (!response.ok) {
      throw new Error('巡检问题分布读取失败')
    }
    const payload = (await response.json()) as DistResponse
    distMonth.value = payload.month
    distStations.value = payload.stations ?? []
    byStation.value = payload.by_station ?? []
    byPerson.value = payload.by_person ?? []
    distEntries.value = payload.entries ?? []
    excluded.value = payload.excluded ?? []
    distEmptyReason.value = payload.empty_reason ?? ''
    stats.value = [
      { label: '本月发现问题', value: payload.month_total ?? 0 },
      { label: '纳入分布巡检单', value: distEntries.value.length },
      { label: '未计入记录', value: excluded.value.length },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检问题分布读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadDistribution()
})
</script>
