<template>
  <div class="flex flex-1 flex-col overflow-hidden">
    <div
      v-if="missing.length"
      class="mx-3 mt-3 rounded-lg bg-surface-amber-1 px-3 py-2 text-p-sm text-ink-amber-3"
    >
      Còn thiếu: {{ missing.join(', ') }}
    </div>
    <SidePanelLayout
      :sections="sections"
      doctype="CRM Lead"
      :docname="leadId"
      :showEmpty="true"
      :highlight="REQUIRED.map((r) => r[0])"
      @reload="emit('reload')"
      @beforeFieldChange="(v) => emit('beforeFieldChange', v)"
      @afterFieldChange="afterFieldChange"
    >
      <template #default="{ section }">
        <LeadRegistrations
          v-if="section.name == 'registrations_section'"
          :registrations="profile.data?.registrations || []"
          :loading="profile.loading"
          :canRegister="canRegister"
          @register="emit('register')"
        />
      </template>
      <template #after-fields="{ section }">
        <LeadBotSummary
          v-if="section.name == 'bot_section'"
          :bot="profile.data?.bot"
          :quizzes="profile.data?.quizzes || []"
        />
        <LeadReferrals
          v-else-if="section.name == 'source_section'"
          :referrals="profile.data?.referrals || []"
        />
      </template>
    </SidePanelLayout>
  </div>
</template>
<script setup>
// Sao Việt (D-122): the customer's side panel, every field grouped (setup.LEAD_SIDE_PANEL) plus the cards no field
// layout can draw: registrations, the bot's conversation and level tests, the people the customer referred.
import SidePanelLayout from '@/components/SidePanelLayout.vue'
import LeadRegistrations from './LeadRegistrations.vue'
import LeadBotSummary from './LeadBotSummary.vue'
import LeadReferrals from './LeadReferrals.vue'
import { useDocument } from '@/data/document'
import { createResource } from 'frappe-ui'
import { computed, watch } from 'vue'

const props = defineProps({
  sections: { type: Array, default: () => [] },
  leadId: { type: String, required: true },
  canRegister: { type: Boolean, default: true },
})
const emit = defineEmits([
  'reload',
  'beforeFieldChange',
  'afterFieldChange',
  'register',
])

// what the bot needs before a consultant takes over (the required Bot Slots)
const REQUIRED = [
  ['course_interest', 'Khóa học'],
  ['territory', 'Chi nhánh'],
  ['mobile_no', 'SĐT'],
]

const { document } = useDocument('CRM Lead', props.leadId)

const missing = computed(() =>
  document.doc
    ? REQUIRED.filter(([field]) => !document.doc[field]).map((r) => r[1])
    : [],
)

const profile = createResource({
  url: 'mmm_custom.customer_profile.profile',
  params: { lead: props.leadId },
  cache: ['customerProfile', props.leadId],
  auto: true,
})

// a registration made or changed elsewhere (Ghi danh, the Deal page) moves the Lead: show it
watch(
  () => [document.doc?.status, document.doc?.converted],
  () => profile.reload(),
)

function afterFieldChange(v) {
  profile.reload()
  emit('afterFieldChange', v)
}
</script>
