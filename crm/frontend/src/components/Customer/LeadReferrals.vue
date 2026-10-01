<template>
  <div v-if="referrals.length" class="flex flex-col gap-1 px-3 pb-1 pt-3">
    <span class="text-sm text-ink-gray-5">
      Khách đã giới thiệu {{ referrals.length }} người
    </span>
    <div
      v-for="r in referrals"
      :key="r.name"
      class="flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-1 text-base hover:bg-surface-gray-2"
      @click="router.push({ name: 'Lead', params: { leadId: r.name } })"
    >
      <span class="truncate text-ink-gray-8">{{ r.lead_name }}</span>
      <span class="shrink-0 text-p-sm text-ink-gray-5">{{ r.status }}</span>
    </div>
  </div>
</template>
<script setup>
import { useRouter } from 'vue-router'

defineProps({ referrals: { type: Array, default: () => [] } })
const router = useRouter()
</script>
