<template>
  <div v-if="schedule" class="px-3 pb-1 pt-3">
    <div
      v-if="card.data"
      class="flex flex-col gap-1 rounded-lg bg-surface-gray-1 p-3 text-p-sm"
    >
      <div class="flex items-center justify-between gap-2">
        <span class="truncate text-base-medium text-ink-gray-8">
          {{ card.data.course_name }}
        </span>
        <Badge
          :label="STATUS[card.data.status] || card.data.status"
          :theme="card.data.status == 'Open' ? 'green' : 'gray'"
          variant="subtle"
        />
      </div>
      <span class="text-ink-gray-6">
        Khai giảng {{ dateVi(card.data.start_date) }} ·
        {{ card.data.shift || 'chưa có ca' }}
      </span>
      <span v-if="card.data.weekdays" class="text-ink-gray-6">
        Học {{ card.data.weekdays }}
      </span>
      <span class="tabular-nums text-ink-gray-6">
        <template v-if="card.data.seats">
          {{ card.data.taken }}/{{ card.data.seats }} chỗ ·
          <span
            :class="
              card.data.seats_left ? 'text-ink-green-3' : 'text-ink-red-3'
            "
          >
            {{
              card.data.seats_left
                ? 'còn ' + card.data.seats_left + ' chỗ'
                : 'hết chỗ'
            }}
          </span>
        </template>
        <template v-else>{{ card.data.taken }} học viên giữ chỗ</template>
      </span>
    </div>
  </div>
</template>
<script setup>
// Sao Việt (D-122): the class a registration is in, with the seats left (customer_profile.class_card)
import { dateVi } from './format'
import { Badge, createResource } from 'frappe-ui'
import { watch } from 'vue'

const props = defineProps({ schedule: { type: String, default: '' } })

const STATUS = { Open: 'Đang nhận', Full: 'Đã đủ', Started: 'Đã khai giảng' }

const card = createResource({
  url: 'mmm_custom.customer_profile.class_card',
  makeParams: () => ({ schedule: props.schedule }),
})

watch(
  () => props.schedule,
  (schedule) => schedule && card.reload(),
  { immediate: true },
)
</script>
