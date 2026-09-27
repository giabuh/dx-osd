<template>
  <Dialog
    v-model:open="show"
    :title="
      quiz
        ? `Sửa bài test ${quiz.config.subject || quiz.title}`
        : 'Thêm bài test'
    "
    size="4xl"
  >
    <template #default>
      <div class="flex flex-col gap-5">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <FormControl
            v-model="form.subject"
            label="Môn"
            placeholder="Excel"
            class="sm:col-span-2"
          />
          <FormControl
            v-model="form.mode"
            type="select"
            label="Kiểu bài"
            :options="MODES"
          />
          <FormControl
            v-model="form.max_questions"
            label="Số câu mỗi lần"
            inputmode="numeric"
          />
        </div>
        <p class="-mt-2 text-p-sm text-ink-gray-5">
          {{ MODE_HELP[form.mode] }}
        </p>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <MultiSelect
            v-model="form.groups"
            label="Mời khi khách quan tâm nhóm khóa"
            placeholder="Chọn nhóm"
            :options="groupOptions"
          >
            <template #summary="{ summary, selectedOptions }">
              {{ joined(selectedOptions, 'label') || summary }}
            </template>
          </MultiSelect>
          <MultiSelect
            v-model="form.courses"
            label="…hoặc các khóa (ưu tiên hơn nhóm)"
            placeholder="Chọn khóa"
            :options="courseOptions"
          >
            <template #summary="{ summary, selectedOptions }">
              {{ joined(selectedOptions, 'value') || summary }}
            </template>
          </MultiSelect>
        </div>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormControl
            v-if="form.mode === 'test'"
            v-model="form.stop_after_wrong"
            label="Dừng sớm khi sai bao nhiêu câu cơ bản (0 = không dừng)"
            inputmode="numeric"
          />
          <FormControl
            v-model="form.active"
            type="checkbox"
            label="Đang dùng (bot được mời khách làm)"
            class="self-end"
          />
        </div>

        <section class="flex flex-col gap-3">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-base-medium text-ink-gray-8">
                Câu hỏi ({{ form.questions.length }})
              </div>
              <div class="text-p-sm text-ink-gray-5">
                Bot hỏi từ câu cơ bản đến nâng cao; câu gắn mục tiêu chỉ hỏi
                khách có mục tiêu đó. Mỗi lựa chọn tối đa 20 ký tự (nút
                Messenger).
              </div>
            </div>
            <Button label="Thêm câu hỏi" iconLeft="plus" @click="addQuestion" />
          </div>
          <div
            v-for="(q, qi) in form.questions"
            :key="q.id"
            class="flex flex-col gap-3 rounded border border-outline-gray-2 p-3"
          >
            <div class="flex items-start gap-2">
              <span class="mt-1.5 text-base-medium text-ink-gray-5">
                {{ qi + 1 }}.
              </span>
              <FormControl
                v-model="q.q"
                class="flex-1"
                placeholder="Nội dung câu hỏi"
              />
              <Button
                variant="ghost"
                icon="arrow-up"
                :disabled="qi === 0"
                @click="move(qi, -1)"
              />
              <Button
                variant="ghost"
                icon="arrow-down"
                :disabled="qi === form.questions.length - 1"
                @click="move(qi, 1)"
              />
              <Button
                variant="ghost"
                icon="trash-2"
                @click="form.questions.splice(qi, 1)"
              />
            </div>
            <div class="grid grid-cols-1 gap-2 pl-5 sm:grid-cols-2">
              <div
                v-for="(_, oi) in q.options"
                :key="oi"
                class="flex items-center gap-2"
              >
                <input
                  v-if="form.mode === 'test'"
                  type="radio"
                  :name="`answer-${q.id}`"
                  :checked="q.answer === oi"
                  :title="'Đáp án đúng'"
                  @change="q.answer = oi"
                />
                <FormControl
                  v-model="q.options[oi]"
                  class="flex-1"
                  :maxlength="20"
                  :placeholder="`Lựa chọn ${oi + 1}`"
                />
                <FormControl
                  v-if="form.mode === 'survey'"
                  v-model="q.points[oi]"
                  class="w-20"
                  inputmode="numeric"
                  placeholder="Điểm"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 gap-2 pl-5 sm:grid-cols-3">
              <FormControl
                v-if="form.mode === 'test'"
                v-model="q.level"
                type="select"
                :options="QUESTION_LEVELS"
              />
              <FormControl
                v-model="q.topic"
                placeholder="Chủ đề (vd VLOOKUP) — báo tư vấn viên khi sai"
                :class="form.mode === 'test' ? '' : 'sm:col-span-2'"
              />
              <MultiSelect
                v-model="q.goals"
                placeholder="Mọi mục tiêu"
                :options="goalOptions"
              >
                <template #summary="{ summary, selectedOptions }">
                  {{ joined(selectedOptions, 'label') || summary }}
                </template>
              </MultiSelect>
            </div>
          </div>
        </section>

        <section class="flex flex-col gap-3">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-base-medium text-ink-gray-8">
                Xếp trình độ theo điểm
              </div>
              <div class="text-p-sm text-ink-gray-5">
                {{
                  form.mode === 'test'
                    ? 'Điểm = số câu đúng.'
                    : 'Điểm = tổng điểm các lựa chọn.'
                }}
                Khách nhận mức đầu tiên có “điểm tối đa” không nhỏ hơn điểm của
                mình.
              </div>
            </div>
            <Button label="Thêm mức" iconLeft="plus" @click="addBand" />
          </div>
          <div
            v-for="(b, bi) in form.bands"
            :key="bi"
            class="grid grid-cols-[6rem_1fr_2fr_auto] items-center gap-2"
          >
            <FormControl
              v-model="b.max"
              inputmode="numeric"
              placeholder="Điểm ≤"
            />
            <FormControl
              v-model="b.level"
              type="select"
              :options="levelOptions"
            />
            <FormControl
              v-model="b.course"
              type="select"
              :options="bandCourseOptions"
            />
            <Button
              variant="ghost"
              icon="trash-2"
              @click="form.bands.splice(bi, 1)"
            />
          </div>
        </section>

        <section class="flex flex-col gap-3">
          <div>
            <div class="text-base-medium text-ink-gray-8">Lời bot nói</div>
            <div class="text-p-sm text-ink-gray-5">
              Xưng “em”, gọi khách “anh/chị” qua
              <code v-pre>{{ brand.me }}</code> và
              <code v-pre>{{ brand.you }}</code
              >; mở đầu bằng “Dạ”, có “ạ”, tối đa 1 emoji. Dùng được
              <code v-pre>{{ quiz.question }}</code
              >, <code v-pre>{{ quiz.step }}</code
              >, <code v-pre>{{ quiz.total }}</code
              >, <code v-pre>{{ quiz.score }}</code
              >, <code v-pre>{{ quiz.level_label }}</code
              >, <code v-pre>{{ quiz.course_name }}</code
              >.
            </div>
          </div>
          <FormControl
            v-for="[key, label] in data.variants"
            :key="key"
            v-model="form.templates[key]"
            type="textarea"
            :rows="4"
            :label="label"
          />
        </section>
        <ErrorMessage class="whitespace-pre-line" :message="error" />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button label="Huỷ" @click="show = false" />
        <Button variant="solid" label="Lưu" :loading="saving" @click="save" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
// One level quiz (a Bot Skill with action level_quiz), saved through mmm_custom.quiz_admin.save_quiz.
import { adminCall } from './adminApi'
import { Dialog, ErrorMessage, FormControl, MultiSelect } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  quiz: { type: Object, default: null },
  data: { type: Object, required: true },
})
const emit = defineEmits(['saved'])
const show = defineModel({ type: Boolean })

const MODES = [
  { label: 'Kiểm tra kiến thức', value: 'test' },
  { label: 'Khảo sát (hỏi phụ huynh)', value: 'survey' },
]
const MODE_HELP = {
  test: 'Mỗi câu có một đáp án đúng. Bot khen khi đúng, động viên khi sai.',
  survey:
    'Không có đúng sai: mỗi lựa chọn có điểm, hợp để hỏi phụ huynh về bé.',
}
const QUESTION_LEVELS = [
  { label: 'Cơ bản', value: 'basic' },
  { label: 'Trung bình', value: 'intermediate' },
  { label: 'Nâng cao', value: 'advanced' },
]
const OPTIONS_PER_QUESTION = 4

let nextId = 0
function question(q = {}) {
  const options = [...(q.options || [])]
  while (options.length < OPTIONS_PER_QUESTION) options.push('')
  const points = options.map((_, i) => String(q.points?.[i] ?? ''))
  return {
    id: nextId++,
    q: q.q || '',
    options,
    answer: q.answer ?? 0,
    points,
    level: q.level || 'basic',
    topic: q.topic || '',
    goals: [...(q.goals || [])],
  }
}

const config = props.quiz?.config || {}
const form = reactive({
  subject: config.subject || '',
  mode: config.mode || 'test',
  max_questions: String(config.max_questions || 5),
  stop_after_wrong: String(config.stop_after_wrong ?? 2),
  groups: [...(config.groups || [])],
  courses: [...(config.courses || [])],
  active: props.quiz ? props.quiz.active : true,
  questions: (config.questions || [{}]).map(question),
  bands: (config.bands || [{ max: 2, level: 'beginner', course: '' }]).map(
    (b) => ({ max: String(b.max), level: b.level, course: b.course || '' }),
  ),
  templates: { ...props.data.defaults, ...(props.quiz?.templates || {}) },
})
// Keep the saved wording even when a template is empty on the server.
for (const [key, text] of Object.entries(props.quiz?.templates || {})) {
  if (!text) form.templates[key] = props.data.defaults[key]
}

const groupOptions = computed(() =>
  props.data.groups.map((g) => ({ label: g, value: g })),
)
const courseOptions = computed(() =>
  props.data.courses.map((c) => ({
    label: `${c.name} (${c.code})`,
    value: c.code,
  })),
)
const bandCourseOptions = computed(() => [
  { label: 'Khóa gợi ý…', value: '' },
  ...courseOptions.value,
])
const levelOptions = computed(() =>
  props.data.levels.map((l) => ({ label: l.label, value: l.value })),
)
const goalOptions = computed(() =>
  props.data.goals.map((g) => ({ label: g.label, value: g.value })),
)

// MultiSelect shows "N selected" past one choice; list them instead (course codes are short).
const joined = (options, key) => options.map((o) => o[key]).join(', ')

function addQuestion() {
  form.questions.push(question())
}
function move(index, step) {
  const [q] = form.questions.splice(index, 1)
  form.questions.splice(index + step, 0, q)
}
function addBand() {
  const last = form.bands[form.bands.length - 1]
  form.bands.push({
    max: String(Number(last?.max || 0) + 1),
    level: 'advanced',
    course: '',
  })
}

const error = ref('')
const saving = ref(false)

function payload() {
  const survey = form.mode === 'survey'
  return {
    subject: form.subject,
    mode: form.mode,
    max_questions: form.max_questions,
    stop_after_wrong: survey ? 0 : form.stop_after_wrong,
    groups: form.groups,
    courses: form.courses,
    questions: form.questions.map((q) => ({
      q: q.q,
      options: q.options,
      ...(survey ? { points: q.points } : { answer: q.answer }),
      level: survey ? '' : q.level,
      topic: q.topic,
      goals: q.goals,
    })),
    bands: form.bands,
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const saved = await adminCall('mmm_custom.quiz_admin.save_quiz', {
      skill: props.quiz?.key || '',
      title: props.quiz?.title || '',
      aliases: props.quiz?.aliases || '',
      active: form.active ? 1 : 0,
      config: JSON.stringify(payload()),
      templates: JSON.stringify(form.templates),
    })
    emit('saved', saved)
    show.value = false
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>
