<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Giao việc</h2>
        <p class="text-p-base text-ink-gray-6">
          Hệ thống tìm việc đang nằm sai người (chưa ai nhận, người cũ đã nghỉ,
          đang offline mà sắp đến hạn, đang quá tải) và đề xuất người nhận. Chỉ
          khi bạn duyệt, việc mới được giao.
        </p>
      </div>
      <div class="flex gap-2">
        <Button
          v-if="proposals.length"
          variant="subtle"
          label="Duyệt tất cả"
          iconLeft="check-check"
          :loading="busy === 'all'"
          @click="approveAll"
        />
        <Button
          variant="solid"
          label="Phân tích & đề xuất"
          iconLeft="sparkles"
          :loading="busy === 'run'"
          @click="analyse"
        />
      </div>
    </div>
    <ErrorMessage :message="error" />
    <div
      v-if="notice"
      class="rounded bg-surface-green-2 px-4 py-3 text-p-base text-ink-gray-9"
    >
      {{ notice }}
    </div>

    <section class="flex flex-col gap-3">
      <h3 class="text-base-semibold text-ink-gray-8">
        Đề xuất chờ duyệt ({{ proposals.length }})
      </h3>
      <div
        v-if="!proposals.length && !loading"
        class="rounded border border-dashed border-outline-gray-2 px-4 py-6 text-center text-p-base text-ink-gray-5"
      >
        Không có đề xuất nào. Bấm “Phân tích & đề xuất” để kiểm tra lại các việc
        đang mở.
      </div>
      <div
        v-for="p in proposals"
        :key="p.task"
        class="flex flex-col gap-3 rounded shadow p-4"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="flex min-w-0 flex-col gap-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-base-medium text-ink-gray-9">{{ p.title }}</span>
              <Badge
                :label="PRIORITY[p.priority] || p.priority"
                :theme="p.priority === 'High' ? 'red' : 'gray'"
              />
            </div>
            <div class="text-p-sm text-ink-gray-5">
              <template v-if="p.customer">Khách: {{ p.customer }} · </template>
              Hạn: {{ displayTime(p.due) }}
              <a
                v-if="p.reference_doctype === 'CRM Lead' && p.reference_docname"
                class="ml-2 text-ink-blue-3 hover:underline"
                :href="`/crm/leads/${p.reference_docname}`"
                target="_blank"
                >Mở khách hàng</a
              >
            </div>
          </div>
          <div class="flex items-center gap-2 text-p-base text-ink-gray-8">
            <span>{{ p.from_name || 'Chưa ai nhận' }}</span>
            <span class="lucide-arrow-right size-4 text-ink-gray-5" />
            <span class="font-medium">{{ chosen[p.task] ? nameOf(chosen[p.task]) : p.to_name }}</span>
          </div>
        </div>
        <p class="text-p-sm text-ink-gray-6">{{ p.reason }}</p>
        <div class="flex flex-wrap items-center gap-2">
          <Button
            variant="solid"
            label="Duyệt"
            :loading="busy === p.task"
            @click="approve(p)"
          />
          <Button
            variant="subtle"
            label="Từ chối"
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
    </section>

    <section class="flex flex-col gap-3">
      <h3 class="text-base-semibold text-ink-gray-8">
        Việc đang mở của từng người
      </h3>
      <div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="person in team"
          :key="person.user"
          class="flex items-center justify-between rounded px-3 py-2 shadow"
        >
          <div class="flex min-w-0 flex-col">
            <span class="truncate text-base-medium text-ink-gray-9">{{ person.name }}</span>
            <span class="text-p-sm text-ink-gray-5">
              {{ person.branch || 'Tổng đài' }} · {{ LEVEL_LABELS[person.level] || person.level }}
            </span>
          </div>
          <Badge
            :label="`${person.open} việc`"
            :theme="person.open >= maxOpen ? 'red' : person.open >= maxOpen / 2 ? 'orange' : 'green'"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { adminCall, displayTime, LEVEL_LABELS } from './adminApi'
import { Badge, Button, ErrorMessage, Select } from 'frappe-ui'
import { onActivated, reactive, ref } from 'vue'

const PRIORITY = { High: 'Cao', Medium: 'Trung bình', Low: 'Thấp' }

const proposals = ref([])
const team = ref([])
const maxOpen = ref(8)
const chosen = reactive({})
const loading = ref(true)
const busy = ref('')
const error = ref('')
const notice = ref('')

const nameOf = (user) => team.value.find((p) => p.user === user)?.name || user

// "" keeps the proposed person; any other consultant can be picked instead.
function optionsFor(p) {
  return [
    { label: `Giao cho ${p.to_name} (đề xuất)`, value: '' },
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
    maxOpen.value = data.max_open
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function run(name, action, done) {
  busy.value = name
  notice.value = ''
  try {
    const result = await action()
    notice.value = done(result)
    await load()
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
    (r) =>
      r.count
        ? `Có ${r.count} đề xuất mới, chờ bạn duyệt.`
        : 'Các việc đang mở đều đã đúng người.',
  )

const approve = (p) =>
  run(
    p.task,
    () =>
      adminCall('mmm_custom.task_dispatch.approve', {
        task: p.task,
        assignee: chosen[p.task] || undefined,
      }),
    () => `Đã giao việc “${p.title}”.`,
  )

const reject = (p) =>
  run(
    p.task,
    () => adminCall('mmm_custom.task_dispatch.reject', { task: p.task }),
    () => `Đã giữ nguyên việc “${p.title}”.`,
  )

const approveAll = () =>
  run(
    'all',
    () => adminCall('mmm_custom.task_dispatch.approve_all'),
    (r) => `Đã giao ${r.count} việc.`,
  )

onActivated(load)
</script>
