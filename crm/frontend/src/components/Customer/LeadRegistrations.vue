<template>
  <div class="flex flex-col gap-2 px-3 pb-1 pt-2">
    <div
      v-if="loading && !registrations.length"
      class="flex items-center gap-2 py-3 text-base text-ink-gray-5"
    >
      <LoadingIndicator class="size-4" /> Đang tải…
    </div>
    <div
      v-for="r in registrations"
      :key="r.name"
      class="flex cursor-pointer flex-col gap-1.5 rounded-lg border border-outline-gray-2 p-3 hover:bg-surface-gray-1"
      @click="router.push({ name: 'Deal', params: { dealId: r.name } })"
    >
      <div class="flex items-center justify-between gap-2">
        <span class="truncate text-base-medium text-ink-gray-9">
          {{ r.course || 'Chưa chọn khóa' }}
        </span>
        <Badge :label="r.label" :theme="r.colour" variant="subtle" />
      </div>
      <div class="truncate text-p-sm text-ink-gray-6">
        {{ r.class_title || 'Chưa xếp lớp' }}
        <template v-if="r.start_date">
          · khai giảng {{ dateVi(r.start_date) }}</template
        >
      </div>
      <div
        v-if="r.final_fee"
        class="flex items-center justify-between text-p-sm tabular-nums"
      >
        <span class="text-ink-gray-6">Đã đóng {{ vnd(r.paid) }}</span>
        <span :class="r.balance > 0 ? 'text-ink-amber-3' : 'text-ink-green-3'">
          {{ r.balance > 0 ? 'Còn ' + vnd(r.balance) : 'Đã đóng đủ' }}
        </span>
      </div>
    </div>
    <div
      v-if="!loading && !registrations.length"
      class="flex flex-col items-start gap-2 py-1 text-p-sm text-ink-gray-5"
    >
      Khách chưa có hồ sơ đăng ký.
      <Button
        v-if="canRegister"
        label="Ghi danh"
        iconLeft="plus"
        @click="emit('register')"
      />
    </div>
  </div>
</template>
<script setup>
import { dateVi, vnd } from './format'
import { Badge, LoadingIndicator } from 'frappe-ui'
import { useRouter } from 'vue-router'

defineProps({
  registrations: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  canRegister: { type: Boolean, default: true },
})
const emit = defineEmits(['register'])
const router = useRouter()
</script>
