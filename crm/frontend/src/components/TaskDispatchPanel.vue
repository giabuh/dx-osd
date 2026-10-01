<template>
  <div v-if="canDispatch" class="border-b border-outline-gray-1 px-5 py-3">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <button
        class="flex items-center gap-2 text-base-medium text-ink-gray-9"
        @click="open = !open"
      >
        <span
          class="size-4 text-ink-gray-5"
          :class="open ? 'lucide-chevron-down' : 'lucide-chevron-right'"
          aria-hidden="true"
        />
        {{ __('Đề xuất giao việc') }}
        <Badge
          v-if="loaded"
          :label="String(proposals.length)"
          :theme="proposals.length ? 'orange' : 'green'"
        />
      </button>
      <div class="flex items-center gap-2">
        <span v-if="notice" class="text-p-sm text-ink-gray-6">{{ notice }}</span>
        <Button
          v-if="proposals.length > 1"
          variant="subtle"
          size="sm"
          :label="__('Duyệt tất cả')"
          iconLeft="lucide-check-check"
          :loading="busy === 'all'"
          @click="approveAll"
        />
        <Button
          variant="subtle"
          size="sm"
          :label="__('Phân tích & đề xuất')"
          iconLeft="lucide-sparkles"
          :loading="busy === 'run'"
          @click="analyse"
        />
      </div>
    </div>
    <ErrorMessage class="mt-2" :message="error" />

    <div v-if="open" class="mt-3 flex max-h-96 flex-col gap-2 overflow-y-auto">
      <p class="text-p-sm text-ink-gray-5">
        {{
          __(
            'Hệ thống tìm việc đang nằm sai người (chưa ai nhận, người cũ đã nghỉ, đang offline mà sắp đến hạn, đang quá tải) và đề xuất người nhận. Chỉ khi bạn duyệt, việc mới được giao.',
          )
        }}
      </p>
      <div
        v-if="loaded && !proposals.length"
        class="rounded border border-dashed border-outline-gray-2 px-4 py-4 text-center text-p-base text-ink-gray-5"
      >
        {{ __('Không có đề xuất nào. Các việc đang mở đều đúng người.') }}
      </div>
      <div
        v-for="p in proposals"
        :key="p.task"
        class="flex flex-col gap-2 rounded p-3 shadow"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="flex min-w-0 flex-col gap-0.5">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-base-medium text-ink-gray-9">{{ p.title }}</span>
              <Badge
                :label="PRIORITY[p.priority] || p.priority"
                :theme="p.priority === 'High' ? 'red' : 'gray'"
              />
            </div>
            <div class="text-p-sm text-ink-gray-5">
              <template v-if="p.customer">{{ p.customer }} · </template>
              {{ __('Hạn') }}: {{ displayTime(p.due) }}
              <a
                v-if="p.reference_doctype === 'CRM Lead' && p.reference_docname"
                class="ml-2 text-ink-gray-7 underline"
                :href="`/crm/leads/${p.reference_docname}`"
                target="_blank"
                >{{ __('Mở khách hàng') }}</a
              >
            </div>
          </div>
          <div class="flex items-center gap-2 text-p-base text-ink-gray-8">
            <span>{{ p.from_name || __('Chưa ai nhận') }}</span>
            <span class="lucide-arrow-right size-4 text-ink-gray-5" />
            <span class="font-medium">{{ targetName(p) }}</span>
          </div>
        </div>
        <p class="text-p-sm text-ink-gray-6">{{ p.reason }}</p>
        <div class="flex flex-wrap items-center gap-2">
          <Button
            variant="solid"
            size="sm"
            :label="__('Duyệt')"
            :loading="busy === p.task"
            @click="approve(p)"
          />
          <Button
            variant="subtle"
            size="sm"
            :label="__('Từ chối')"
            :disabled="busy === p.task"
            @click="reject(p)"
          />
          <Select
            v-model="chosen[p.task]"
            class="w-full sm:w-64"
            :options="optionsFor(p)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Task dispatch (D-124): the system proposes who should take a task, a manager decides. Only managers see this;
// the server checks the role again on every call (mmm_custom.task_dispatch).
import { adminCall, displayTime } from '@/components/Admin/adminApi'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/users'
import { Badge, Button, ErrorMessage, Select } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'

const emit = defineEmits(['changed'])

const KEEP = 'proposed' // the select's default: the proposed person
const PRIORITY = { High: 'Cao', Medium: 'Trung bình', Low: 'Thấp' }

const session = sessionStore()
const { isManager } = usersStore()
const canDispatch = computed(
  () => session.user === 'Administrator' || isManager(session.user),
)

const proposals = ref([])
const team = ref([])
const chosen = reactive({})
const open = ref(false)
const loaded = ref(false)
const busy = ref('')
const error = ref('')
const notice = ref('')

const nameOf = (user) => team.value.find((p) => p.user === user)?.name || user
const targetName = (p) =>
  chosen[p.task] && chosen[p.task] !== KEEP ? nameOf(chosen[p.task]) : p.to_name

function optionsFor(p) {
  return [
    { label: `Giao cho ${p.to_name} (đề xuất)`, value: KEEP },
    ...team.value
      .filter((person) => person.user !== p.to && person.user !== p.from)
      .map((person) => ({
        label: `${person.name} · ${person.open} việc`,
        value: person.user,
      })),
  ]
}

async function load() {
  try {
    const data = await adminCall('mmm_custom.task_dispatch.overview')
    proposals.value = data.proposals
    team.value = data.team
    for (const p of data.proposals) chosen[p.task] ||= KEEP
    if (!loaded.value && data.proposals.length) open.value = true
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loaded.value = true
  }
}

// Run one action, say what happened, refresh the proposals and tell the page its task list changed.
async function run(name, action, done) {
  busy.value = name
  notice.value = ''
  try {
    notice.value = done(await action())
    await load()
    emit('changed')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}

const analyse = () =>
  run(
    'run',
    () => adminCall('mmm_custom.task_dispatch.propose'),
    (r) => {
      open.value = r.count > 0 || open.value
      return r.count
        ? `Có ${r.count} đề xuất mới.`
        : 'Các việc đang mở đều đúng người.'
    },
  )

const approve = (p) =>
  run(
    p.task,
    () =>
      adminCall('mmm_custom.task_dispatch.approve', {
        task: p.task,
        assignee: chosen[p.task] === KEEP ? undefined : chosen[p.task],
      }),
    () => `Đã giao “${p.title}”.`,
  )

const reject = (p) =>
  run(
    p.task,
    () => adminCall('mmm_custom.task_dispatch.reject', { task: p.task }),
    () => `Đã giữ nguyên “${p.title}”.`,
  )

const approveAll = () =>
  run(
    'all',
    () => adminCall('mmm_custom.task_dispatch.approve_all'),
    (r) => `Đã giao ${r.count} việc.`,
  )

onMounted(() => {
  if (canDispatch.value) load()
})
</script>
