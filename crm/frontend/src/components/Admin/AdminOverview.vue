<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Tổng quan</h2>
        <p class="text-p-base text-ink-gray-6">{{ subtitle }}</p>
      </div>
      <div
        class="inline-flex gap-0.5 rounded-lg bg-surface-gray-2 p-0.5"
        role="group"
        aria-label="Chọn khoảng thời gian"
      >
        <button
          v-for="option in PERIODS"
          :key="option.value"
          type="button"
          class="rounded-md px-3 py-1 text-base"
          :class="
            period === option.value
              ? 'bg-surface-white text-ink-gray-9 shadow'
              : 'text-ink-gray-6 hover:text-ink-gray-8'
          "
          :aria-pressed="period === option.value"
          @click="period = option.value"
        >
          {{ option.label }}
        </button>
      </div>
    </div>
    <ErrorMessage :message="error" />
    <div
      v-if="period === 'today' && data && !totals.leads"
      class="rounded bg-surface-amber-1 px-3 py-2 text-p-base text-ink-amber-3"
    >
      Hôm nay chưa có khách mới. Chọn “7 ngày” để xem bức tranh đầy đủ.
    </div>

    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <!-- a literal <button>: :is="'button'" would resolve to the global frappe-ui Button (h-7) -->
      <button
        v-for="card in cards"
        :key="card.title"
        type="button"
        class="flex flex-col gap-1 rounded px-4 py-3 text-left shadow hover:shadow-md"
        title="Mở danh sách khách này"
        @click="card.open()"
      >
        <span class="text-p-sm text-ink-gray-6">{{ card.title }}</span>
        <span class="text-2xl font-semibold tabular-nums text-ink-gray-9">{{
          card.value.toLocaleString('vi-VN')
        }}</span>
        <span class="text-p-sm text-ink-gray-5">{{ card.hint }}</span>
      </button>
    </div>

    <div
      class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]"
    >
      <div class="flex flex-col gap-3 rounded p-4 shadow">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <span class="text-base-medium text-ink-gray-8"
            >Hành trình khách hàng</span
          >
          <span class="text-p-sm text-ink-gray-5"
            >Bấm một bước để mở danh sách khách</span
          >
        </div>
        <button
          v-for="(stage, i) in funnel"
          :key="stage.stage"
          type="button"
          class="grid grid-cols-[120px_minmax(0,1fr)_44px] items-center gap-2.5 rounded text-left hover:bg-surface-gray-1 sm:grid-cols-[140px_minmax(0,1fr)_48px]"
          @click="openStage(i)"
        >
          <span class="text-p-sm text-ink-gray-7">{{ stage.stage }}</span>
          <span class="relative h-6 overflow-hidden rounded bg-surface-gray-1">
            <span
              class="absolute inset-y-0 left-0 rounded transition-[width] duration-300"
              :class="
                i === funnel.length - 1
                  ? 'bg-surface-green-3'
                  : 'bg-surface-gray-7'
              "
              :style="{ width: `${stage.width}%` }"
            />
            <span
              class="absolute inset-y-0 flex items-center text-sm font-semibold tabular-nums"
              :class="stage.width >= 14 ? 'text-ink-white' : 'text-ink-gray-9'"
              :style="
                stage.width >= 14
                  ? { right: `calc(${100 - stage.width}% + 8px)` }
                  : { left: `calc(${stage.width}% + 6px)` }
              "
              >{{ stage.count.toLocaleString('vi-VN') }}</span
            >
          </span>
          <span
            class="text-right text-p-sm tabular-nums text-ink-gray-5"
            :title="i ? 'So với số Lead mới' : ''"
            >{{ stage.pct }}</span
          >
        </button>
        <span class="text-p-xs text-ink-gray-5"
          >% ở cột phải: so với số Lead mới trong kỳ</span
        >
      </div>

      <div class="flex flex-col gap-4 rounded p-4 shadow">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <span class="text-base-medium text-ink-gray-8">Học phí</span>
          <span class="text-p-sm text-ink-gray-5"
            >Từ phiếu ghi danh trong kỳ</span
          >
        </div>
        <div>
          <div class="text-2xl font-semibold tabular-nums text-ink-gray-9">
            {{ money(fees.paid) }}
          </div>
          <div class="text-p-sm text-ink-gray-6">
            đã thu từ {{ fees.registrations || 0 }} học viên đăng ký
          </div>
        </div>
        <div class="flex h-2.5 overflow-hidden rounded-full bg-surface-gray-2">
          <span class="bg-surface-green-3" :style="{ width: `${paidPct}%` }" />
          <span
            class="bg-surface-amber-2"
            :style="{ width: `${feesTotal ? 100 - paidPct : 0}%` }"
          />
        </div>
        <div class="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-p-base">
          <span class="flex items-center gap-2 text-ink-gray-7"
            ><span class="size-2.5 rounded-sm bg-surface-green-3" />Đã
            đóng</span
          >
          <span class="text-right font-medium tabular-nums text-ink-gray-9">{{
            money(fees.paid)
          }}</span>
          <span class="flex items-center gap-2 text-ink-gray-7"
            ><span class="size-2.5 rounded-sm bg-surface-amber-2" />Còn phải
            thu</span
          >
          <span class="text-right font-medium tabular-nums text-ink-gray-9">{{
            money(fees.due)
          }}</span>
        </div>
        <div
          class="mt-auto flex flex-wrap gap-x-5 gap-y-1 border-t border-outline-gray-1 pt-3 text-p-sm text-ink-gray-6"
        >
          <button
            type="button"
            class="hover:text-ink-gray-9"
            @click="openList('Deals', { status: 'Pending Payment' })"
          >
            <b class="font-semibold text-ink-gray-9">{{
              fees.pending_payment || 0
            }}</b>
            chờ đóng phí
          </button>
          <span
            >Độ phủ tri thức
            <b class="font-semibold text-ink-gray-9"
              >{{ data?.coverage ?? 0 }}%</b
            ></span
          >
        </div>
      </div>
    </div>

    <div class="rounded shadow">
      <div class="px-5 pt-4 text-base-medium text-ink-gray-8">
        Khách tiềm năng mới nhất
      </div>
      <ListView
        class="px-3 pb-2"
        :columns="columns"
        :rows="leads"
        row-key="name"
        :options="{
          selectable: false,
          getRowRoute: (row) => ({
            name: 'Lead',
            params: { leadId: row.name },
          }),
          emptyState: {
            title: 'Chưa có khách trong khoảng thời gian này',
            description: 'Chọn khoảng thời gian dài hơn ở góc trên',
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
import { adminCall, displayTime, money } from './adminApi'
import { Badge, ErrorMessage, ListView } from 'frappe-ui'
import { computed, onActivated, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// Same keys as mmm_custom.engine.dashboard.PERIODS; 7 days by default, as "today" is often empty.
const PERIODS = [
  { label: 'Hôm nay', value: 'today' },
  { label: '7 ngày', value: '7' },
  { label: '30 ngày', value: '30' },
  { label: '90 ngày', value: '90' },
]
const HOT_THEME = { Nóng: 'red', Ấm: 'orange', Lạnh: 'blue' }
// The Lead statuses each funnel step counts (lifecycle.reached: that step or a later one).
const QUALIFIED_ON = [
  'Qualified',
  'Contacted',
  'Nurture',
  'Trial Booked',
  'Converted',
]
const TRIAL_ON = ['Trial Booked', 'Converted']

const period = ref('30')  // same default as engine/dashboard.DEFAULT_PERIOD
const data = ref(null)
const error = ref('')

const totals = computed(() => data.value?.totals || {})
const fees = computed(() => data.value?.fees || {})
const feesTotal = computed(() => (fees.value.paid || 0) + (fees.value.due || 0))
const paidPct = computed(() =>
  feesTotal.value ? Math.round((100 * fees.value.paid) / feesTotal.value) : 0,
)

const subtitle = computed(() => {
  if (!data.value) return 'Hành trình khách hàng và học phí'
  const day = (value) => value.split('-').reverse().slice(0, 2).join('/')
  if (period.value === 'today') return `Hôm nay · ${day(data.value.since)}`
  const label = PERIODS.find((p) => p.value === period.value).label
  return `${label} qua · từ ${day(data.value.since)}`
})

function openList(name, filters = {}) {
  router.push({
    name,
    params: { viewType: 'list' },
    query: {
      filters: JSON.stringify({
        creation: ['>=', data.value?.since],
        ...filters,
      }),
    },
  })
}
const openLeads = (filters = {}) => openList('Leads', filters)

// One click target per funnel step, in the order of customers.build's funnel.
const STAGE_FILTERS = [
  () => openLeads(),
  () => openLeads({ mobile_no: ['is', 'set'] }),
  () => openLeads({ status: ['in', QUALIFIED_ON] }),
  () => openLeads({ lead_owner: ['is', 'set'] }),
  () => openLeads({ status: ['in', TRIAL_ON] }),
  () => openList('Deals'),
]
const openStage = (i) => STAGE_FILTERS[i]?.()

const cards = computed(() => {
  const t = totals.value
  const share = (n) => (t.leads ? Math.round((100 * n) / t.leads) : 0)
  return [
    {
      title: 'Lead mới',
      value: t.leads ?? 0,
      hint: `${t.hot ?? 0} khách nóng`,
      open: () => openLeads(),
    },
    {
      title: 'Đủ thông tin',
      value: t.qualified ?? 0,
      hint: `${share(t.qualified ?? 0)}% số Lead`,
      open: () => openLeads({ status: ['in', QUALIFIED_ON] }),
    },
    {
      title: 'Đã giao tư vấn',
      value: t.assigned ?? 0,
      hint: 'bot giao theo chi nhánh',
      open: () => openLeads({ lead_owner: ['is', 'set'] }),
    },
    {
      title: 'Đã đăng ký',
      value: t.converted ?? 0,
      hint: `tỉ lệ chốt ${share(t.converted ?? 0)}%`,
      open: () => openList('Deals'),
    },
  ]
})

const funnel = computed(() => {
  const rows = data.value?.funnel || []
  const top = Math.max(1, rows[0]?.count || 0)
  // each step as a share of the new Leads: steps are not strictly nested (a Lead can be handed to a consultant
  // before it is qualified), so "of the step before" showed 164%
  const first = rows[0]?.count || 0
  return rows.map((row, i) => ({
    ...row,
    width: row.count ? Math.max(3, Math.round((100 * row.count) / top)) : 0,
    pct: !i ? '' : first ? `${Math.round((100 * row.count) / first)}%` : '—',
  }))
})

const columns = [
  { label: 'Khách hàng', key: 'customer', width: 1.6 },
  { label: 'Nhóm khóa', key: 'groups', width: 1.6 },
  { label: 'Chi nhánh', key: 'territory', width: 1.3 },
  { label: 'Độ nóng', key: 'hotness', width: 0.9 },
  { label: 'Trạng thái', key: 'status', width: 1.1 },
  { label: 'Phụ trách', key: 'owner', width: 1.4 },
  { label: 'Thời gian', key: 'time', width: 1.2 },
]
const leads = computed(() =>
  (data.value?.latest || []).map((row) => ({
    ...row,
    time: displayTime(row.creation),
  })),
)

async function load() {
  try {
    data.value = await adminCall('mmm_custom.engine.dashboard.overview', {
      period: period.value,
    })
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}
watch(period, load)
onActivated(load)
</script>
