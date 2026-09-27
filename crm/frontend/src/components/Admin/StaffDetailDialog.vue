<template>
  <Dialog v-model:open="show" :title="person.full_name || person.name" size="lg">
    <template #default>
      <div class="flex flex-col gap-4">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-p-base text-ink-gray-6">{{ person.name }}</span>
          <Badge
            :label="person.active ? 'Đang làm' : 'Đã nghỉ'"
            :theme="person.active ? 'green' : 'gray'"
          />
          <Badge v-if="person.handles_b2b" label="Khách doanh nghiệp" />
        </div>
        <dl class="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-3 text-p-base">
          <dt class="text-ink-gray-5">Chi nhánh</dt>
          <dd class="text-ink-gray-8">{{ branchLabel }}</dd>
          <dt class="text-ink-gray-5">Cấp bậc</dt>
          <dd class="text-ink-gray-8">
            {{ LEVEL_LABELS[person.level] || person.level || '—' }}
          </dd>
          <dt class="text-ink-gray-5">Chuyên môn</dt>
          <dd class="flex flex-wrap gap-1.5">
            <Badge
              v-for="group in person.specialties || []"
              :key="group"
              :label="group"
              theme="blue"
            />
            <span v-if="!person.specialties?.length" class="text-ink-gray-5">
              Chưa chọn nhóm khóa học
            </span>
          </dd>
          <dt class="text-ink-gray-5">Chatwoot</dt>
          <dd>
            <Badge
              v-if="person.chatwoot_agent_id"
              label="Đã đồng bộ"
              theme="green"
            />
            <Badge
              v-else-if="person.active"
              label="Đang đồng bộ…"
              theme="orange"
            />
            <span v-else class="text-ink-gray-5">—</span>
          </dd>
        </dl>
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions>
      <div class="flex flex-wrap justify-end gap-2">
        <Button
          v-if="canSwitch && person.active"
          label="Xem với tư cách nhân viên này"
          iconLeft="log-in"
          :loading="switching"
          @click="viewAs"
        />
        <Button
          variant="solid"
          label="Sửa thông tin"
          iconLeft="edit-2"
          @click="emit('edit', person)"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { LEVEL_LABELS } from './adminApi'
import { switchToStaff } from '@/composables/staffSwitch'
import { Badge, Dialog, ErrorMessage } from 'frappe-ui'
import { computed, ref } from 'vue'

const props = defineProps({
  person: { type: Object, required: true },
  canSwitch: { type: Boolean, default: false },
})
const emit = defineEmits(['edit'])
const show = defineModel({ type: Boolean })

const error = ref('')
const switching = ref(false)
const branchLabel = computed(
  () =>
    props.person.branch ||
    (props.person.handles_b2b ? 'Doanh nghiệp (B2B)' : 'Tổng đài'),
)

// Demo: a System Manager opens the CRM as this consultant (mmm_custom.staff_switch).
async function viewAs() {
  switching.value = true
  try {
    await switchToStaff(props.person.name)
  } catch (e) {
    error.value = e.message
    switching.value = false
  }
}
</script>
