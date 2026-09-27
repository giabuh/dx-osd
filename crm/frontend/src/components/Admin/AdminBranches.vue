<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Chi nhánh</h2>
        <p class="text-p-base text-ink-gray-6">
          Bot hỏi khách theo khu vực → chi nhánh, rồi giao cho nhân viên của chi
          nhánh đó
        </p>
      </div>
      <Button
        variant="solid"
        label="Thêm chi nhánh"
        iconLeft="plus"
        @click="edit(null)"
      />
    </div>
    <ErrorMessage :message="error" />
    <ListView
      :columns="columns"
      :rows="groups"
      row-key="name"
      :options="{
        selectable: false,
        emptyState: {
          title: 'Chưa có chi nhánh',
          description: 'Bấm “Thêm chi nhánh” để tạo',
        },
        onRowClick: (row) => edit(row),
      }"
    >
      <template #group-header="{ group }">
        <span class="text-base-medium text-ink-gray-8">
          {{ group.group }}
        </span>
        <span class="ml-1 text-base text-ink-gray-5">
          · {{ group.rows.length }} chi nhánh
        </span>
      </template>
      <template #cell="{ item, column, row }">
        <Button
          v-if="column.key === 'staff'"
          variant="ghost"
          :label="`${item} người`"
          @click.stop="openStaff(row.name)"
        />
        <div
          v-else
          class="truncate text-base"
          :class="column.key === 'name' ? 'text-ink-gray-9' : 'text-ink-gray-7'"
        >
          {{ item || '—' }}
        </div>
      </template>
    </ListView>
    <BranchDialog
      v-if="showDialog"
      v-model="showDialog"
      :branch="selected"
      :areas="data.areas"
      @saved="load"
    />
  </div>
</template>

<script setup>
import BranchDialog from './BranchDialog.vue'
import { adminCall } from './adminApi'
import { ErrorMessage, ListView } from 'frappe-ui'
import { computed, onActivated, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const data = ref({ areas: [], branches: [] })
const error = ref('')
const showDialog = ref(false)
const selected = ref(null)

const columns = [
  { label: 'Chi nhánh', key: 'name', width: 1.6 },
  { label: 'Mã', key: 'branch_code', width: 0.8 },
  { label: 'Địa chỉ', key: 'address', width: 3 },
  { label: 'Hotline', key: 'hotline', width: 1.1 },
  { label: 'Nhân viên', key: 'staff', width: 0.9 },
]

// ListView groups rows given as [{ group, rows }]: one group per area.
const groups = computed(() =>
  data.value.areas.map((area) => ({
    group: area,
    collapsed: false,
    rows: data.value.branches.filter((branch) => branch.area === area),
  })),
)

async function load() {
  try {
    data.value = await adminCall('mmm_custom.bot_admin.branches')
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

function edit(branch) {
  selected.value = branch
  showDialog.value = true
}

function openStaff(branch) {
  router.push({ name: 'Admin', params: { tab: 'staff' }, query: { branch } })
}

onActivated(load)
</script>
