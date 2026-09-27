import { defineStore } from 'pinia'

/** 巡检任务页的筛选状态：列表筛选与分布视图的站点范围都存在这里，
 * 从巡检单详情返回列表时按这里存的口径恢复，保证两处筛选范围、各站点条数一致。
 */
export const useInspectionStore = defineStore('inspection', {
  state: () => ({
    filters: {} as Record<string, string>,
    station: '',
  }),
  actions: {
    setFilters(filters: Record<string, string>) {
      this.filters = { ...filters }
    },
    setStation(station: string) {
      this.station = station
    },
  },
})
