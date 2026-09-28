<template>
  <Dialog v-model:open="show" title="Chọn Fanpage để kết nối" size="3xl">
    <template #default>
      <div class="flex flex-col gap-4">
        <p v-if="accountName" class="text-p-base text-ink-gray-6">
          Tài khoản Facebook: <b class="text-ink-gray-8">{{ accountName }}</b
          >. Chọn page và chi nhánh phụ trách. Page không chọn chi nhánh thì bot
          tư vấn trước rồi giao cho đúng nhân viên.
        </p>
        <div v-if="!rows.length" class="text-base text-ink-gray-6">
          Tài khoản này không quản lý page nào.
        </div>
        <div class="flex flex-col divide-y divide-outline-gray-1">
          <div
            v-for="row in rows"
            :key="row.id"
            class="flex items-center gap-3 py-2.5"
            :class="row.can_message ? '' : 'opacity-60'"
          >
            <input
              v-model="row.selected"
              type="checkbox"
              class="size-4 rounded"
              :disabled="!row.can_message"
            />
            <img
              v-if="row.picture"
              :src="row.picture"
              class="size-8 rounded-full"
              alt=""
            />
            <div
              v-else
              class="flex size-8 items-center justify-center rounded-full bg-surface-gray-3 text-sm text-ink-gray-7"
            >
              {{ row.name.slice(0, 1) }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="truncate text-base-medium text-ink-gray-9">
                {{ row.name }}
              </div>
              <div class="truncate text-sm text-ink-gray-5">
                {{ row.category || row.id }}
                <span v-if="!row.can_message">
                  · Tài khoản không có quyền nhắn tin của page này
                </span>
              </div>
            </div>
            <Badge
              v-if="row.connected"
              label="Đã kết nối"
              theme="green"
              variant="subtle"
            />
            <select
              v-model="row.branch"
              class="form-select w-48 text-base"
              :disabled="!row.selected"
            >
              <option value="">Không gắn chi nhánh</option>
              <option v-for="b in branches" :key="b" :value="b">{{ b }}</option>
            </select>
          </div>
        </div>
        <div v-if="results.length" class="flex flex-col gap-1">
          <div
            v-for="r in results"
            :key="r.id"
            class="text-base"
            :class="r.ok ? 'text-ink-green-3' : 'text-ink-red-4'"
          >
            {{ r.ok ? '✓' : '✗' }} {{ r.name }}:
            {{
              r.ok
                ? `đã tạo inbox #${r.inbox_id}, ${r.lead_forms} form Lead Ads`
                : r.error
            }}
          </div>
        </div>
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button label="Đóng" @click="show = false" />
        <Button
          variant="solid"
          :label="`Kết nối ${selectedCount} page`"
          :disabled="!selectedCount"
          :loading="saving"
          @click="connect"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { adminCall } from './adminApi'
import { Badge, Dialog, ErrorMessage } from 'frappe-ui'
import { computed, ref } from 'vue'

const props = defineProps({
  // { account_name, pages } from mmm_custom.channels.facebook.pages
  data: { type: Object, required: true },
  branches: { type: Array, default: () => [] },
})
const emit = defineEmits(['connected'])
const show = defineModel({ type: Boolean })

const accountName = props.data.account_name
const rows = ref(
  (props.data.pages || []).map((page) => ({
    ...page,
    selected: page.can_message && !page.connected,
  })),
)
const saving = ref(false)
const error = ref('')
const results = ref([])

const selectedCount = computed(
  () => rows.value.filter((r) => r.selected).length,
)

async function connect() {
  saving.value = true
  error.value = ''
  try {
    const pages = rows.value
      .filter((r) => r.selected)
      .map((r) => ({ id: r.id, branch: r.branch || '' }))
    results.value = await adminCall('mmm_custom.channels.facebook.connect', {
      pages: JSON.stringify(pages),
    })
    for (const r of results.value) {
      const row = rows.value.find((x) => x.id === r.id)
      if (row && r.ok) {
        row.connected = true
        row.selected = false
      }
    }
    emit('connected')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>
