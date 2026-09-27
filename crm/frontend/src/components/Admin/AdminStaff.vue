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
        onRowClick: (row) => edit(row.person),
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
        <Badge
          v-else-if="column.key === 'chatwoot' && row.person.chatwoot_agent_id"
          label="Đã đồng bộ"
          theme="green"
        />
        <Badge
          v-else-if="column.key === 'chatwoot' && row.person.active"
          label="Đang đồng bộ…"
          theme="amber"
        />
        <Button
          v-else-if="column.key === 'switch' && canSwitch && row.person.active"
          variant="ghost"
          label="Xem như"
          iconLeft="log-in"
          :loading="switching === row.name"
          @click.stop="viewAs(row.name)"
        />
        <div v-else-if="column.key === 'switch'" />
        <div v-else class="truncate text-base text-ink-gray-7">
          {{ item || '—' }}
        </div>
      </template>
    </ListView>
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
import StaffDialog from './StaffDialog.vue'
import { adminCall, LEVEL_LABELS } from './adminApi'
import { staffSwitch, switchToStaff } from '@/composables/staffSwitch'
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
const switching = ref('')
// Demo: a System Manager opens the CRM as this consultant (mmm_custom.staff_switch).
const canSwitch = computed(() => Boolean(staffSwitch.data?.can_switch))

async function viewAs(user) {
  switching.value = user
  try {
    await switchToStaff(user)
  } catch (e) {
    error.value = e.message
    switching.value = ''
  }
}

const columns = [
  { label: 'Nhân viên', key: 'full_name', width: 2.4 },
  { label: 'Chi nhánh', key: 'branch', width: 1.6 },
  { label: 'Cấp bậc', key: 'level', width: 1.1 },
  { label: 'Chuyên môn', key: 'specialties', width: 2.2 },
  { label: 'Trạng thái', key: 'status', width: 1 },
  { label: 'Chatwoot', key: 'chatwoot', width: 1.2 },
  { label: '', key: 'switch', width: 1 },
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
      specialties: (s.specialties || []).join(', '),
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

function edit(person) {
  selected.value = person
  showDialog.value = true
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
