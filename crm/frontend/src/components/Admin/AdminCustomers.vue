<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Khách hàng</h2>
        <p class="text-p-base text-ink-gray-6">
          Khách đến từ đâu, quan tâm gì, ai đang phụ trách và vì sao
        </p>
      </div>
      <Select v-model="days" class="w-full sm:w-48" :options="periods" />
    </div>
    <ErrorMessage :message="error" />

    <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
      <div
        v-for="card in cards"
        :key="card.title"
        class="overflow-hidden rounded shadow"
      >
        <NumberChart :config="card" />
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div class="h-80 rounded shadow">
        <AxisChart v-if="data" :config="funnelChart" />
      </div>
      <div class="h-80 overflow-hidden rounded shadow">
        <DonutChart v-if="data" :config="groupChart" />
      </div>
    </div>

    <div class="rounded shadow">
      <div class="px-5 pt-4">
        <div class="text-base-medium text-ink-gray-8">Nguồn khách</div>
        <div class="text-p-sm text-ink-gray-5">
          Mọi kênh đổ về cùng một hộp thư, cùng bot và cùng luật phân công —
          thêm kênh mới không phải làm lại CRM
        </div>
      </div>
      <div class="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="source in data?.sources || []"
          :key="source.key"
          class="flex flex-col gap-1 rounded border border-outline-gray-1 p-3"
          :class="source.status === 'planned' ? 'bg-surface-gray-1' : ''"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="truncate text-base-medium text-ink-gray-8">
              {{ source.label }}
            </span>
            <Badge
              :label="STATUS[source.status]?.label || 'Khác'"
              :theme="STATUS[source.status]?.theme || 'gray'"
            />
          </div>
          <div class="text-2xl-semibold text-ink-gray-9">
            {{ source.status === 'planned' ? '—' : source.count }}
          </div>
          <div class="text-p-sm text-ink-gray-5">{{ source.how }}</div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div class="h-80 rounded shadow">
        <AxisChart v-if="data" :config="branchChart" />
      </div>
      <div class="h-80 overflow-hidden rounded shadow">
        <DonutChart v-if="data" :config="hotnessChart" />
      </div>
    </div>

    <div class="rounded shadow">
      <div class="px-5 pt-4">
        <div class="text-base-medium text-ink-gray-8">
          Bảng xếp hạng tư vấn viên
        </div>
        <div class="text-p-sm text-ink-gray-5">
          Xếp theo số ghi danh, rồi số khách tiềm năng
        </div>
      </div>
      <ListView
        class="px-3 pb-2"
        :columns="staffColumns"
        :rows="staffRows"
        row-key="user"
        :options="{
          selectable: false,
          emptyState: {
            title: 'Chưa có khách được giao',
            description: 'Khi bot chuyển khách, tư vấn viên sẽ hiện ở đây',
          },
        }"
      >
        <template #cell="{ item, column, row }">
          <div v-if="column.key === 'full_name'" class="flex flex-col truncate">
            <span class="truncate text-base text-ink-gray-9">
              {{ row.rank }}. {{ item }}
            </span>
            <span class="truncate text-p-sm text-ink-gray-5">
              {{ row.level }}
            </span>
          </div>
          <Progress
            v-else-if="column.key === 'rate'"
            :value="item"
            :label="`${item}%`"
            size="sm"
          />
          <div v-else class="truncate text-base text-ink-gray-7">
            {{ item }}
          </div>
        </template>
      </ListView>
    </div>

    <div class="rounded shadow">
      <div class="px-5 pt-4">
        <div class="text-base-medium text-ink-gray-8">Khách mới nhất</div>
        <div class="text-p-sm text-ink-gray-5">
          Cột “Vì sao” là lý do bot chọn người phụ trách
        </div>
      </div>
      <ListView
        class="px-3 pb-2"
        :columns="leadColumns"
        :rows="leadRows"
        row-key="name"
        :options="{
          selectable: false,
          getRowRoute: (row) => ({
            name: 'Lead',
            params: { leadId: row.name },
          }),
          emptyState: {
            title: 'Chưa có khách trong khoảng thời gian này',
            description: 'Đổi khoảng thời gian ở góc trên',
          },
        }"
      >
        <template #cell="{ item, column }">
          <Badge
            v-if="column.key === 'hotness'"
            :label="item"
            :theme="HOT_THEME[item] || 'gray'"
          />
          <div v-else class="truncate text-base text-ink-gray-7" :title="item">
            {{ item || '—' }}
          </div>
        </template>
      </ListView>
    </div>
  </div>
</template>

<script setup>
import { adminCall, displayTime } from './adminApi'
import {
  AxisChart,
  Badge,
  DonutChart,
  ErrorMessage,
  ListView,
  NumberChart,
  Progress,
  Select,
} from 'frappe-ui'
import { computed, onActivated, ref, watch } from 'vue'

const STATUS = {
  live: { label: 'Đang chạy', theme: 'green' },
  ready: { label: 'Sẵn sàng kết nối', theme: 'blue' },
  planned: { label: 'Sắp tích hợp', theme: 'orange' },
  manual: { label: 'Nhân viên nhập', theme: 'gray' },
}
const HOT_THEME = { Nóng: 'red', Ấm: 'orange', Lạnh: 'blue' }

const periods = [
  { label: '7 ngày qua', value: '7' },
  { label: '30 ngày qua', value: '30' },
  { label: '90 ngày qua', value: '90' },
  { label: '12 tháng qua', value: '365' },
]
const days = ref('30')
const data = ref(null)
const error = ref('')

const cards = computed(() => {
  const t = data.value?.totals || {}
  return [
    { title: 'Lead mới', value: t.leads ?? 0 },
    { title: 'Có số điện thoại', value: t.with_phone ?? 0 },
    { title: 'Khách tiềm năng', value: t.qualified ?? 0 },
    { title: 'Khách nóng', value: t.hot ?? 0 },
    { title: 'Khách doanh nghiệp', value: t.b2b ?? 0 },
    { title: 'Đã ghi danh', value: t.converted ?? 0 },
  ]
})

const funnelChart = computed(() => ({
  data: data.value?.funnel || [],
  title: 'Phễu khách hàng',
  subtitle: 'Từ lúc nhắn tin đến khi ghi danh',
  xAxis: { key: 'stage', type: 'category', title: 'Giai đoạn' },
  yAxis: { title: 'Số khách' },
  swapXY: true,
  series: [
    {
      name: 'count',
      type: 'bar',
      echartOptions: { colorBy: 'data' },
    },
  ],
}))

const groupChart = computed(() => ({
  data: data.value?.groups || [],
  title: 'Nhóm khóa học quan tâm',
  subtitle: 'Một khách có thể quan tâm nhiều nhóm',
  categoryColumn: 'name',
  valueColumn: 'count',
}))

const branchChart = computed(() => ({
  data: data.value?.branches || [],
  title: 'Khách theo chi nhánh',
  subtitle: 'Chi nhánh khách chọn khi chat',
  xAxis: { key: 'name', type: 'category', title: 'Chi nhánh' },
  yAxis: { title: 'Số khách' },
  swapXY: true,
  series: [{ name: 'count', type: 'bar' }],
}))

const hotnessChart = computed(() => ({
  data: data.value?.hotness || [],
  title: 'Mức độ sẵn sàng đăng ký',
  subtitle: 'AI đọc từ cuộc chat',
  categoryColumn: 'name',
  valueColumn: 'count',
}))

const staffColumns = [
  { label: 'Tư vấn viên', key: 'full_name', width: 2 },
  { label: 'Chi nhánh', key: 'branch', width: 1.5 },
  { label: 'Khách được giao', key: 'leads', width: 1 },
  { label: 'Tiềm năng', key: 'qualified', width: 1 },
  { label: 'Ghi danh', key: 'converted', width: 1 },
  { label: 'Tỷ lệ chốt', key: 'rate', width: 1.4 },
]

const staffRows = computed(() =>
  (data.value?.consultants || []).map((row, index) => ({
    ...row,
    rank: index + 1,
    level: row.level === 'Team Lead' ? 'Trưởng nhóm' : 'Tư vấn viên',
  })),
)

const leadColumns = [
  { label: 'Khách hàng', key: 'customer', width: 1.6 },
  { label: 'Nguồn', key: 'source', width: 1.4 },
  { label: 'Nhóm khóa', key: 'groups', width: 1.6 },
  { label: 'Chi nhánh', key: 'territory', width: 1.3 },
  { label: 'Phụ trách', key: 'owner', width: 1.4 },
  { label: 'Trạng thái', key: 'status', width: 1.1 },
  { label: 'Độ nóng', key: 'hotness', width: 0.9 },
  { label: 'Vì sao', key: 'why', width: 2.4 },
  { label: 'Thời gian', key: 'time', width: 1.2 },
]

const leadRows = computed(() =>
  (data.value?.latest || []).map((row) => ({
    ...row,
    time: displayTime(row.creation),
  })),
)

async function load() {
  try {
    data.value = await adminCall('mmm_custom.engine.customers.overview', {
      days: days.value,
    })
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

watch(days, load)
onActivated(load)
</script>
