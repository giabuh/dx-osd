<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Bài test trình độ</h2>
        <p class="text-p-base text-ink-gray-6">
          Bot tự mời khách làm khi đã biết khóa khách quan tâm mà chưa rõ trình
          độ. Làm xong khách được xếp lớp, nhận buổi học thử và mã ưu đãi khi để
          lại số điện thoại.
        </p>
      </div>
      <div class="flex w-full gap-2 sm:w-auto">
        <Select v-model="days" class="flex-1 sm:w-44" :options="periods" />
        <Button
          variant="solid"
          label="Thêm bài test"
          iconLeft="plus"
          :disabled="!data"
          @click="edit(null)"
        />
      </div>
    </div>
    <ErrorMessage :message="error" />

    <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
      <div
        v-for="card in cards"
        :key="card.title"
        class="overflow-hidden rounded shadow"
      >
        <NumberChart :config="card" />
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div class="h-80 rounded shadow">
        <AxisChart v-if="funnel" :config="funnelChart" />
      </div>
      <div class="h-80 rounded shadow">
        <AxisChart v-if="funnel" :config="quizChart" />
      </div>
    </div>

    <div class="rounded shadow">
      <div class="px-5 pt-4">
        <div class="text-base-medium text-ink-gray-8">Các bài test</div>
        <div class="text-p-sm text-ink-gray-5">
          Bấm một dòng để sửa câu hỏi, cách xếp trình độ và lời bot nói
        </div>
      </div>
      <ListView
        class="px-3 pb-2"
        :columns="columns"
        :rows="rows"
        row-key="key"
        :options="{
          selectable: false,
          onRowClick: (row) => edit(row.quiz),
          emptyState: {
            title: 'Chưa có bài test',
            description: 'Thêm một bài test để bot mời khách làm',
          },
        }"
      >
        <template #cell="{ item, column, row }">
          <div v-if="column.key === 'subject'" class="flex flex-col truncate">
            <span class="truncate text-base text-ink-gray-9">{{ item }}</span>
            <span class="truncate text-p-sm text-ink-gray-5">
              {{ row.kind }}
            </span>
          </div>
          <Badge
            v-else-if="column.key === 'status'"
            :label="row.quiz.active ? 'Đang dùng' : 'Tắt'"
            :theme="row.quiz.active ? 'green' : 'gray'"
          />
          <Progress
            v-else-if="column.key === 'rate'"
            :value="item"
            :label="`${item}%`"
            size="sm"
          />
          <div v-else class="truncate text-base text-ink-gray-7" :title="item">
            {{ item ?? '—' }}
          </div>
        </template>
      </ListView>
    </div>

    <QuizDialog
      v-if="showDialog"
      v-model="showDialog"
      :quiz="selected"
      :data="data"
      @saved="load"
    />
  </div>
</template>

<script setup>
// Level tests (mmm_custom.quiz_admin): what Jev offers, how it places customers, and how many it brings in.
import QuizDialog from './QuizDialog.vue'
import { adminCall } from './adminApi'
import {
  AxisChart,
  Badge,
  ErrorMessage,
  ListView,
  NumberChart,
  Progress,
  Select,
} from 'frappe-ui'
import { computed, onActivated, ref, watch } from 'vue'

const periods = [
  { label: '7 ngày qua', value: '7' },
  { label: '30 ngày qua', value: '30' },
  { label: '90 ngày qua', value: '90' },
  { label: '12 tháng qua', value: '365' },
]
const STAGES = [
  ['offered', 'Được mời'],
  ['started', 'Làm bài'],
  ['done', 'Làm xong'],
  ['phone', 'Để lại SĐT'],
  ['enrolled', 'Ghi danh'],
]

const days = ref('30')
const data = ref(null)
const funnel = ref(null)
const error = ref('')
const showDialog = ref(false)
const selected = ref(null)

const counts = (key) => funnel.value?.quizzes.find((q) => q.key === key)?.counts
const total = (stage) =>
  (funnel.value?.quizzes || []).reduce((sum, q) => sum + q.counts[stage], 0)

const cards = computed(() => [
  ...STAGES.map(([stage, title]) => ({ title, value: total(stage) })),
  {
    title: 'Quay lại nhờ nhắc',
    value: total('recovered'),
    delta: total('reminded'),
    deltaSuffix: ' được nhắc',
  },
])

const funnelChart = computed(() => ({
  data: STAGES.map(([stage, label]) => ({ stage: label, count: total(stage) })),
  title: 'Phễu bài test',
  subtitle: 'Từ lời mời của bot đến khi khách ghi danh',
  xAxis: { key: 'stage', type: 'category', title: 'Giai đoạn' },
  yAxis: { title: 'Số khách' },
  swapXY: true,
  series: [{ name: 'count', type: 'bar', echartOptions: { colorBy: 'data' } }],
}))

const quizChart = computed(() => ({
  data: (funnel.value?.quizzes || []).map((q) => ({
    quiz: subjectOf(q.key) || q.title,
    'Làm bài': q.counts.started,
    'Làm xong': q.counts.done,
    'Để SĐT': q.counts.phone,
  })),
  title: 'Theo từng bài test',
  subtitle: 'Làm bài · làm xong · để lại SĐT',
  xAxis: { key: 'quiz', type: 'category', title: 'Bài test' },
  yAxis: { title: 'Số khách' },
  series: [
    { name: 'Làm bài', type: 'bar' },
    { name: 'Làm xong', type: 'bar' },
    { name: 'Để SĐT', type: 'bar' },
  ],
}))

const subjectOf = (key) =>
  data.value?.quizzes.find((q) => q.key === key)?.config.subject

const columns = [
  { label: 'Bài test', key: 'subject', width: 1.6 },
  { label: 'Mời khi khách quan tâm', key: 'scope', width: 2.2 },
  { label: 'Số câu', key: 'size', width: 0.8 },
  { label: 'Được mời', key: 'offered', width: 0.9 },
  { label: 'Làm xong', key: 'done', width: 0.9 },
  { label: 'Để SĐT', key: 'phone', width: 0.9 },
  { label: 'Làm xong / làm bài', key: 'rate', width: 1.4 },
  { label: 'Trạng thái', key: 'status', width: 1 },
]

const rows = computed(() =>
  (data.value?.quizzes || []).map((quiz) => {
    const c = counts(quiz.key) || {}
    const cfg = quiz.config
    return {
      key: quiz.key,
      quiz,
      subject: cfg.subject || quiz.title,
      kind: cfg.mode === 'survey' ? 'Khảo sát phụ huynh' : 'Kiểm tra kiến thức',
      scope: scopeText(cfg),
      size: `${cfg.max_questions || cfg.questions?.length || 0}/${cfg.questions?.length || 0}`,
      offered: c.offered ?? 0,
      done: c.done ?? 0,
      phone: c.phone ?? 0,
      rate: c.started ? Math.round((100 * c.done) / c.started) : 0,
    }
  }),
)

// "Tin học văn phòng · 5 khóa", or the course codes when the quiz only names a few courses.
function scopeText(cfg) {
  const groups = cfg.groups || []
  const courses = cfg.courses || []
  if (!groups.length) return courses.join(', ')
  return courses.length
    ? `${groups.join(', ')} · ${courses.length} khóa`
    : groups.join(', ')
}

function edit(quiz) {
  selected.value = quiz
  showDialog.value = true
}

async function load() {
  try {
    const [quizzes, stats] = await Promise.all([
      adminCall('mmm_custom.quiz_admin.quizzes'),
      adminCall('mmm_custom.quiz_admin.quiz_funnel', { days: days.value }),
    ])
    data.value = quizzes
    funnel.value = stats
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

watch(days, load)
onActivated(load)
</script>
