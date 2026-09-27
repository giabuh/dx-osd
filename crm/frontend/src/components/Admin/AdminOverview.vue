<template>
  <div class="flex flex-col gap-5 p-5">
    <div>
      <h2 class="text-lg-semibold text-ink-gray-9">Tổng quan hôm nay</h2>
      <p class="text-p-base text-ink-gray-6">
        Hoạt động của bot trên Messenger
      </p>
    </div>
    <ErrorMessage :message="error" />
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      <div
        v-for="card in cards"
        :key="card.title"
        class="overflow-hidden rounded shadow"
      >
        <NumberChart :config="card" />
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
            title: 'Chưa có khách tiềm năng từ bot',
            description: 'Lead bot đánh giá tiềm năng sẽ hiện ở đây',
          },
        }"
      />
    </div>
  </div>
</template>

<script setup>
import { adminCall, displayTime } from './adminApi'
import { ErrorMessage, ListView, NumberChart } from 'frappe-ui'
import { computed, onActivated, ref } from 'vue'

const data = ref(null)
const error = ref('')

const cards = computed(() => {
  const d = data.value || {}
  return [
    { title: 'Lead mới hôm nay', value: d.new_today ?? 0 },
    { title: 'Khách tiềm năng hôm nay', value: d.qualified_today ?? 0 },
    { title: 'Không tiềm năng hôm nay', value: d.unqualified_today ?? 0 },
    { title: 'Đã chuyển tư vấn hôm nay', value: d.handed_off_today ?? 0 },
    {
      title: 'Độ phủ tri thức trung bình',
      value: d.coverage ?? 0,
      suffix: '%',
    },
  ]
})

const columns = [
  { label: 'Khách hàng', key: 'customer', width: 2 },
  { label: 'Điện thoại', key: 'mobile_no', width: 1.2 },
  { label: 'Khóa học', key: 'course_interest', width: 2 },
  { label: 'Chi nhánh', key: 'territory', width: 1.3 },
  { label: 'Tư vấn viên', key: 'lead_owner', width: 1.8 },
  { label: 'Thời gian', key: 'time', width: 1.2 },
]

const leads = computed(() =>
  (data.value?.latest_leads || []).map((lead) => ({
    name: lead.name,
    customer: lead.lead_name || lead.first_name || lead.name,
    mobile_no: lead.mobile_no || '—',
    course_interest: lead.course_interest || '—',
    territory: lead.territory || '—',
    lead_owner: lead.lead_owner || '—',
    time: displayTime(lead.creation),
  })),
)

async function load() {
  try {
    data.value = await adminCall('mmm_custom.engine.dashboard.summary')
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

onActivated(load)
</script>
