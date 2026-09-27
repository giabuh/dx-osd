<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Nhân viên</h2>
        <p class="text-p-base text-ink-gray-6">
          Lưu ở đây là tự đồng bộ sang Chatwoot: tài khoản, nhóm chi nhánh
        </p>
      </div>
      <Button
        variant="solid"
        label="Thêm nhân viên"
        iconLeft="plus"
        @click="edit(null)"
      />
    </div>
    <div
      v-if="notice"
      class="rounded bg-surface-blue-2 px-3 py-2 text-p-base text-ink-blue-8"
    >
      {{ notice }}
    </div>
    <ErrorMessage :message="error" />
    <div class="flex flex-wrap items-center gap-2">
      <TextInput
        v-model="search"
        class="w-full sm:w-64"
        placeholder="Tìm tên hoặc email"
        :debounce="200"
      >
        <template #prefix>
          <span
            class="lucide-search size-4 text-ink-gray-5"
            aria-hidden="true"
          />
        </template>
      </TextInput>
      <Select
        v-model="branch"
        class="w-full sm:w-72"
        :options="branchOptions"
      />
    </div>
    <ListView
      :columns="columns"
      :rows="rows"
      row-key="name"
      :options="{
        selectable: false,
        emptyState: {
          title: 'Không có nhân viên phù hợp',
          description: 'Đổi bộ lọc hoặc thêm nhân viên',
        },
        onRowClick: (row) => open(row.person),
      }"
    >
      <template #cell="{ item, column, row }">
        <div v-if="column.key === 'full_name'" class="flex flex-col truncate">
          <span class="truncate text-base text-ink-gray-9">{{ item }}</span>
          <span class="truncate text-p-sm text-ink-gray-5">{{ row.name }}</span>
        </div>
        <Badge
          v-else-if="column.key === 'status'"
          :label="row.person.active ? 'Đang làm' : 'Đã nghỉ'"
          :theme="row.person.active ? 'green' : 'gray'"
        />
        <div v-else class="truncate text-base text-ink-gray-7" :title="item">
          {{ item || '—' }}
        </div>
      </template>
    </ListView>
    <StaffDetailDialog
      v-if="detail"
      v-model="showDetail"
      :person="detail"
      :canSwitch="canSwitch"
      @edit="editFromDetail"
    />
    <StaffDialog
      v-if="showDialog"
      v-model="showDialog"
      :person="selected"
      :data="data"
      :defaultBranch="branch !== NO_BRANCH ? branch : ''"
      @saved="afterSave"
    />
  </div>
</template>

<script setup>
import StaffDetailDialog from './StaffDetailDialog.vue'
import StaffDialog from './StaffDialog.vue'
import { adminCall, LEVEL_LABELS } from './adminApi'
import { staffSwitch } from '@/composables/staffSwitch'
import { Badge, ErrorMessage, ListView, Select, TextInput } from 'frappe-ui'
import { computed, onActivated, onDeactivated, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const NO_BRANCH = '__none'
const route = useRoute()
const router = useRouter()

const data = ref({ staff: [], branches: [], levels: [], groups: [] })
const error = ref('')
const notice = ref('')
const search = ref('')
const branch = ref('')
const showDialog = ref(false)
const selected = ref(null)
let syncPoll = null
const detail = ref(null)
const showDetail = ref(false)
// Demo: a System Manager opens the CRM as this consultant (mmm_custom.staff_switch).
const canSwitch = computed(() => Boolean(staffSwitch.data?.can_switch))

// Compact list; everything else (specialties, Chatwoot sync, actions) lives in StaffDetailDialog.
// minmax(0, …) lets a column shrink below its text, so long names truncate instead of widening the table.
const columns = [
  { label: 'Nhân viên', key: 'full_name', width: 'minmax(0, 2fr)' },
  { label: 'Chi nhánh', key: 'branch', width: 'minmax(0, 1.2fr)' },
  { label: 'Cấp bậc', key: 'level', width: 'minmax(0, 1fr)' },
  { label: 'Trạng thái', key: 'status', width: '7rem' },
]

const branchOptions = computed(() => [
  { label: 'Tất cả chi nhánh', value: '' },
  { label: 'Tổng đài / B2B (không chi nhánh)', value: NO_BRANCH },
  ...data.value.branches.map((name) => ({ label: name, value: name })),
])

const rows = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('vi')
  return data.value.staff
    .filter(
      (s) =>
        (!branch.value ||
          (branch.value === NO_BRANCH
            ? !s.branch
            : s.branch === branch.value)) &&
        `${s.full_name} ${s.name}`.toLocaleLowerCase('vi').includes(query),
    )
    .map((s) => ({
      name: s.name,
      person: s,
      full_name: s.full_name || s.name,
      branch: s.branch || (s.handles_b2b ? 'Doanh nghiệp (B2B)' : 'Tổng đài'),
      level: LEVEL_LABELS[s.level] || s.level,
    }))
})

// The branches tab opens this one filtered: /crm/admin/staff?branch=CN Dĩ An
watch(
  () => route.query.branch,
  (value) => {
    if (value !== undefined) branch.value = value
  },
  { immediate: true },
)
watch(branch, (value) => {
  if (route.params.tab === 'staff' && (route.query.branch || '') !== value) {
    router.replace({ query: value ? { branch: value } : {} })
  }
})

async function load() {
  try {
    data.value = await adminCall('mmm_custom.bot_admin.staff')
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

function open(person) {
  detail.value = person
  showDetail.value = true
}

function edit(person) {
  selected.value = person
  showDialog.value = true
}

function editFromDetail(person) {
  showDetail.value = false
  edit(person)
}

async function afterSave() {
  notice.value = 'Đã lưu. Chatwoot sẽ cập nhật trong vài giây.'
  await load()
  clearTimeout(syncPoll)
  syncPoll = setTimeout(async () => {
    await load()
    notice.value = ''
  }, 8000)
}

onActivated(load)
onDeactivated(() => clearTimeout(syncPoll))
</script>
