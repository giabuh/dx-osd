<template>
  <div v-if="total > 0" class="flex flex-col gap-1.5 px-3 pb-1 pt-3">
    <div class="h-2 overflow-hidden rounded-full bg-surface-gray-2">
      <div
        class="h-full rounded-full"
        :style="{
          width: Math.min((paid / total) * 100, 100) + '%',
          background:
            paid >= total ? 'var(--ink-green-3)' : 'var(--ink-blue-3)',
        }"
      />
    </div>
    <div class="flex items-center justify-between text-p-sm tabular-nums">
      <span class="text-ink-gray-6"
        >Đã đóng {{ vnd(paid) }} / {{ vnd(total) }}</span
      >
      <span :class="paid >= total ? 'text-ink-green-3' : 'text-ink-amber-3'">
        {{ paid >= total ? 'Đã đóng đủ' : 'Còn ' + vnd(total - paid) }}
      </span>
    </div>
  </div>
</template>
<script setup>
// Sao Việt (D-122): how much of the fee a registration has paid
import { vnd } from './format'
import { computed } from 'vue'

const props = defineProps({ doc: { type: Object, default: () => ({}) } })

const total = computed(() => Number(props.doc.final_fee) || 0)
const paid = computed(() => Number(props.doc.paid_amount) || 0)
</script>
