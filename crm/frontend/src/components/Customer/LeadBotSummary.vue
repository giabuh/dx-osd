<template>
  <div v-if="bot || quizzes.length" class="flex flex-col gap-2 px-3 pb-1 pt-3">
    <div
      v-if="bot"
      class="flex flex-col gap-1 rounded-lg bg-surface-gray-1 p-3 text-p-sm"
    >
      <div class="flex items-center justify-between gap-2">
        <span class="text-base-medium text-ink-gray-8">Hội thoại với bot</span>
        <Badge :label="bot.label" :theme="botTheme" variant="subtle" />
      </div>
      <span class="text-ink-gray-6">
        {{ bot.turns }} lượt chat
        <template v-if="bot.consultant">
          · chuyển cho {{ bot.consultant }}</template
        >
        <template v-if="bot.returning"> · khách quay lại</template>
      </span>
    </div>
    <div
      v-for="(q, i) in quizzes"
      :key="i"
      class="flex flex-col gap-0.5 rounded-lg border border-outline-gray-2 p-3 text-p-sm"
    >
      <div class="flex items-center justify-between gap-2">
        <span class="truncate text-ink-gray-8">{{ q.quiz }}</span>
        <span class="shrink-0 text-ink-gray-5">{{ q.label }}</span>
      </div>
      <span v-if="q.score || q.level" class="text-ink-gray-6 tabular-nums">
        {{
          [q.score && 'Điểm ' + q.score, q.level].filter(Boolean).join(' · ')
        }}
      </span>
      <span v-if="q.voucher" class="text-ink-gray-6">
        Mã ưu đãi {{ q.voucher }}
      </span>
    </div>
  </div>
</template>
<script setup>
import { Badge } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  bot: { type: Object, default: null },
  quizzes: { type: Array, default: () => [] },
})

const botTheme = computed(
  () =>
    ({ active: 'blue', handed_off: 'green', closed: 'gray' })[
      props.bot?.status
    ] || 'gray',
)
</script>
