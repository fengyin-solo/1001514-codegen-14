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

    <section class="dist-panel">
      <header class="dist-head">
        <div>
          <h3 class="dist-title">巡检问题分布</h3>
          <p class="page-desc">
            按巡检单号与巡检人员汇总发现问题数；巡检人员或发现问题数未填的巡检单不进入分布，缺失项见下方说明。
          </p>
        </div>
        <label class="filter-item scope-item">
          <span>站点范围</span>
          <select v-model="stationScope" @change="onScopeChange">
            <option value="">全部站点</option>
            <option v-for="station in distStations" :key="station" :value="station">{{ station }}</option>
          </select>
        </label>
      </header>

      <p v-if="dist.message" class="dist-empty">{{ dist.message }}</p>
      <div v-else class="dist-grid">
        <article class="dist-card">
          <h4>按站点分布</h4>
          <ul class="dist-list">
            <li v-for="item in dist.by_station" :key="item.station" class="dist-row">
              <span class="dist-name">{{ item.station }}</span>
              <span class="dist-bar"><i :style="{ width: barWidth(item.issues) }"></i></span>
              <span class="dist-num">{{ item.issues }} 问题 · {{ item.orders }} 单</span>
            </li>
          </ul>
        </article>

        <article class="dist-card">
          <h4>按人员分布</h4>
          <ul class="dist-list">
            <li v-for="item in dist.by_person" :key="item.person" class="dist-person-block">
              <button class="dist-row dist-person" type="button" @click="togglePerson(item.person)">
                <span class="dist-name">{{ item.person }}</span>
                <span class="dist-bar"><i :style="{ width: barWidth(item.issues) }"></i></span>
                <span class="dist-num">{{ item.issues }} 问题 · {{ item.orders }} 单</span>
                <span class="dist-toggle">{{ activePerson === item.person ? '收起' : '巡检单' }}</span>
              </button>
              <div v-if="activePerson === item.person" class="person-orders">
                <p v-if="personOrdersLoading" class="dist-empty">正在读取 {{ item.person }} 名下的巡检单…</p>
                <template v-else-if="personOrders.length">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th>巡检单号</th>
                        <th>巡检站点</th>
                        <th>巡检日期</th>
                        <th>发现问题数</th>
                        <th>巡检状态</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="order in personOrders" :key="String(order.id)">
                        <td>{{ order['巡检单号'] ?? '—' }}</td>
                        <td>{{ order['巡检站点'] ?? '—' }}</td>
                        <td>{{ order['巡检日期'] ?? '—' }}</td>
                        <td>{{ order['发现问题数'] === '' || order['发现问题数'] == null ? '未填' : order['发现问题数'] }}</td>
                        <td>{{ order['巡检状态'] ?? '—' }}</td>
                        <td><button class="link" type="button" @click="openDetail(Number(order.id))">查看</button></td>
                      </tr>
                    </tbody>
                  </table>
                  <p class="dist-note">共 {{ personOrdersTotal }} 张巡检单，范围与当前站点筛选一致</p>
                </template>
                <p v-else class="dist-empty">{{ item.person }} 在当前站点范围内没有巡检单</p>
              </div>
            </li>
          </ul>
        </article>

        <article class="dist-card month-card">
          <h4>本月发现总量</h4>
          <strong class="month-value">{{ dist.month_total }}</strong>
          <span class="dist-note">{{ dist.month }} 内填写完整的巡检单合计</span>
          <span class="dist-note">当前站点范围累计发现 {{ dist.total_issues }} 个问题</span>
        </article>
      </div>

      <div v-if="dist.excluded.length" class="excluded-box">
        <h4>未进入分布的巡检单（{{ dist.excluded.length }} 张）</h4>
        <ul>
          <li v-for="item in dist.excluded" :key="String(item.id)">
            {{ item.order_no }}（{{ item.station }}）：{{ item.missing.join('、') }}
          </li>
        </ul>
      </div>
    </section>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="filterPlaceholders[field]" />
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
          <td v-for="column in columns" :key="column">{{ row[column] === '' || row[column] == null ? '—' : row[column] }}</td>
          <td class="row-actions">
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
          <td :colspan="columns.length + 1" class="empty-state">
            {{ stationScope ? `站点范围「${stationScope}」内暂无巡检任务数据` : '暂无巡检任务数据，可先登记巡检单' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条巡检任务记录{{ stationScope ? `（站点范围：${stationScope}）` : '' }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal-box">
        <h3 class="dist-title">巡检单 {{ detail['巡检单号'] }}</h3>
        <dl class="detail-list">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] === '' || detail[column] == null ? '未填' : detail[column] }}</dd>
          </template>
        </dl>
        <p v-if="detailError" class="error-text">{{ detailError }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeDetail">返回列表</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface StationBucket {
  station: string
  orders: number
  issues: number
}

interface PersonBucket {
  person: string
  orders: number
  issues: number
}

interface ExcludedOrder {
  id: number | string
  order_no: string
  station: string
  missing: string[]
}

interface Distribution {
  month: string
  month_total: number
  total_issues: number
  stations: string[]
  by_station: StationBucket[]
  by_person: PersonBucket[]
  excluded: ExcludedOrder[]
  status_counts: Record<string, number>
  message: string
}

const ENDPOINT = '/api/inspection'
const columns = ["巡检单号", "巡检站点", "巡检人员", "巡检日期", "巡检项目", "发现问题数", "巡检时长", "巡检状态"]
const actions = ["派发巡检", "提交结果", "作废巡检"]

const emptyDist = (): Distribution => ({
  month: '',
  month_total: 0,
  total_issues: 0,
  stations: [],
  by_station: [],
  by_person: [],
  excluded: [],
  status_counts: {},
  message: '',
})

const stats = ref([{ label: '待派发巡检', value: 0 }, { label: '巡检中任务', value: 0 }, { label: '本月发现问题', value: 0 }])
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ 巡检单号: '', 巡检人员: '' })
const filterFields = ['巡检单号', '巡检人员']
const filterPlaceholders: Record<string, string> = {
  巡检单号: '按巡检单号检索',
  巡检人员: '输入完整巡检人员姓名',
}

// 站点范围同时驱动分布视图与下方列表，保证两处筛选范围、各站点条数一致
const stationScope = ref('')
const dist = ref<Distribution>(emptyDist())
const distStations = ref<string[]>([])
const activePerson = ref('')
const personOrders = ref<Row[]>([])
const personOrdersTotal = ref(0)
const personOrdersLoading = ref(false)
const detail = ref<Row | null>(null)
const detailError = ref('')

const maxIssues = computed(() =>
  Math.max(1, ...dist.value.by_station.map((item) => item.issues), ...dist.value.by_person.map((item) => item.issues)),
)

function barWidth(issues: number) {
  return `${Math.max(4, Math.round((issues / maxIssues.value) * 100))}%`
}

function resetFilters() {
  filters.value = { 巡检单号: '', 巡检人员: '' }
  stationScope.value = ''
  activePerson.value = ''
  void reload()
  void loadDistribution()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '巡检单登记入口尚未接入审批流'
}

function onScopeChange() {
  activePerson.value = ''
  void reload()
  void loadDistribution()
}

async function togglePerson(person: string) {
  if (activePerson.value === person) {
    activePerson.value = ''
    return
  }
  activePerson.value = person
  personOrdersLoading.value = true
  try {
    const query = new URLSearchParams({ person, size: '100' })
    if (stationScope.value) {
      query.set('station', stationScope.value)
    }
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('人员名下巡检单读取失败')
    }
    const payload = await response.json()
    personOrders.value = payload.items ?? []
    personOrdersTotal.value = payload.total ?? personOrders.value.length
  } catch (error) {
    personOrders.value = []
    personOrdersTotal.value = 0
    errorMessage.value = error instanceof Error ? error.message : '人员名下巡检单读取失败'
  } finally {
    personOrdersLoading.value = false
  }
}

async function openDetail(id: number) {
  detailError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    if (!response.ok) {
      throw new Error(`巡检单 ${id} 读取失败`)
    }
    detail.value = await response.json()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '巡检单明细读取失败'
  }
}

function closeDetail() {
  // 只关闭弹窗，不重置筛选：返回后列表与分布视图的范围、各站点条数保持原样
  detail.value = null
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
    await reload()
    await loadDistribution()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡检任务操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value['巡检单号']) {
    query.set('keyword', filters.value['巡检单号'])
  }
  if (filters.value['巡检人员']) {
    query.set('person', filters.value['巡检人员'])
  }
  if (stationScope.value) {
    query.set('station', stationScope.value)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
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
  const query = new URLSearchParams()
  if (stationScope.value) {
    query.set('station', stationScope.value)
  }
  try {
    const response = await request(`${ENDPOINT}/distribution?${query.toString()}`)
    if (!response.ok) {
      throw new Error('巡检问题分布读取失败')
    }
    const payload = (await response.json()) as Distribution
    dist.value = { ...emptyDist(), ...payload }
    distStations.value = payload.stations ?? []
    stats.value = [
      { label: '待派发巡检', value: payload.status_counts?.['待派发'] ?? 0 },
      { label: '巡检中任务', value: payload.status_counts?.['巡检中'] ?? 0 },
      { label: '本月发现问题', value: payload.month_total ?? 0 },
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
