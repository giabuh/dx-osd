<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Lớp khai giảng</h2>
        <p class="text-p-base text-ink-gray-6">
          Các lớp sắp khai giảng, số chỗ còn lại. Khách đăng ký chọn lớp trong
          danh sách này
        </p>
      </div>
      <Button
        v-if="options.can_edit"
        variant="solid"
        label="Thêm lớp"
        iconLeft="plus"
        @click="edit(null)"
      />
    </div>
    <div class="flex flex-wrap items-end gap-3">
      <FormControl
        v-model="filters.course"
        class="w-64"
        type="select"
        label="Khóa học"
        :options="courseFilter"
        @change="load"
      />
      <FormControl
        v-model="filters.branch"
        class="w-48"
        type="select"
        label="Chi nhánh"
        :options="branchFilter"
        @change="load"
      />
      <FormControl
        v-model="filters.status"
        class="w-36"
        type="select"
        label="Trạng thái"
        :options="statusFilter"
        @change="load"
      />
      <FormControl
        v-model="filters.include_past"
        type="checkbox"
        label="Cả lớp đã qua"
        @change="load"
      />
    </div>
    <ErrorMessage :message="error" />
    <ListView
      :columns="columns"
      :rows="rows"
      row-key="name"
      :options="{
        selectable: false,
        emptyState: {
          title: 'Không có lớp nào',
          description: 'Đổi bộ lọc hoặc thêm lớp mới',
        },
        onRowClick: (row) => edit(row),
      }"
    >
      <template #cell="{ item, column, row }">
        <Badge
          v-if="column.key === 'status'"
          :label="statusLabel(item)"
          :theme="item === 'Open' ? 'green' : 'gray'"
        />
        <div v-else-if="column.key === 'seats_left'" class="text-base">
          <span v-if="row.seats" class="text-ink-gray-9">
            {{ row.taken }}/{{ row.seats }}
            <span class="text-ink-gray-5"> · còn {{ item }}</span>
          </span>
          <span v-else class="text-ink-gray-5">Không giới hạn</span>
        </div>
        <div v-else-if="column.key === 'pending'" class="text-base">
          <span :class="item ? 'text-ink-amber-3' : 'text-ink-gray-5'">
            {{ item || '—' }}
          </span>
        </div>
        <div v-else class="truncate text-base text-ink-gray-8">
          {{ column.key === 'start_date' ? dateVi(item) : item || '—' }}
        </div>
      </template>
    </ListView>
    <ClassDialog
      v-if="showDialog"
      v-model="showDialog"
      :schedule="selected"
      :options="options"
      :default-branch="filters.branch || options.my_branch"
      @saved="load"
    />
  </div>
</template>

<script setup>
import ClassDialog from './ClassDialog.vue'
import { adminCall } from '@/components/Admin/adminApi'
import { Badge, ErrorMessage, FormControl, ListView } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'

const options = reactive({
  can_edit: false,
  my_branch: '',
  courses: [],
  branches: [],
  shifts: [],
  statuses: [],
})
const filters = reactive({
  course: '',
  branch: '',
  status: 'Open',
  include_past: false,
})
const rows = ref([])
const error = ref('')
const showDialog = ref(false)
const selected = ref(null)

const columns = [
  { label: 'Khóa học', key: 'course_name', width: 2 },
  { label: 'Chi nhánh', key: 'branch', width: 1.3 },
  { label: 'Khai giảng', key: 'start_date', width: 1 },
  { label: 'Ca', key: 'shift', width: 1.4 },
  { label: 'Lịch học', key: 'weekdays', width: 1 },
  { label: 'Chỗ', key: 'seats_left', width: 1.5 },
  { label: 'Chờ xử lý', key: 'pending', width: 0.8 },
  { label: 'Trạng thái', key: 'status', width: 0.8 },
]
const STATUS_LABELS = {
  Open: 'Đang mở',
  Full: 'Đã đủ',
  Started: 'Đã khai giảng',
}
const statusLabel = (value) => STATUS_LABELS[value] || value
const dateVi = (value) => {
  const [y, m, d] = String(value || '')
    .slice(0, 10)
    .split('-')
  return d ? `${d}/${m}/${y}` : ''
}

const all = (label) => [{ label, value: '' }]
const courseFilter = computed(() => [
  ...all('Tất cả khóa'),
  ...options.courses.map((c) => ({ label: c.name, value: c.code })),
])
const branchFilter = computed(() => [
  ...all('Tất cả chi nhánh'),
  ...options.branches.map((b) => ({ label: b, value: b })),
])
const statusFilter = computed(() => [
  ...all('Tất cả'),
  ...options.statuses.map((v) => ({ label: statusLabel(v), value: v })),
])

async function load() {
  try {
    rows.value = await adminCall('mmm_custom.classes.schedules', {
      ...filters,
      include_past: filters.include_past ? 1 : 0,
    })
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

function edit(row) {
  if (!options.can_edit) return
  selected.value = row
  showDialog.value = true
}

onMounted(async () => {
  try {
    Object.assign(options, await adminCall('mmm_custom.classes.context'))
    filters.branch = options.my_branch // consultants start on their own branch
  } catch (e) {
    error.value = e.message
  }
  await load()
})
</script>
