<template>
  <Dialog v-model:open="show" title="Thêm khóa học" size="3xl">
    <template #default>
      <div class="flex flex-col gap-4">
        <p v-if="source" class="text-p-sm text-ink-gray-5">
          Đã đọc từ {{ source }}. Xem lại rồi bấm Lưu.
        </p>
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.product_name"
            label="Tên khóa học"
            placeholder="SQL cho phân tích dữ liệu"
          />
          <FormControl
            v-model="form.product_code"
            label="Mã khóa học"
            placeholder="LT-SQL"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.course_group"
            type="select"
            label="Nhóm khóa học"
            :options="groupOptions"
          />
          <FormControl
            v-model="form.button_label"
            label="Chữ trên nút bot"
            placeholder="Để trống = tên khóa"
            :maxlength="20"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.standard_rate"
            label="Học phí (đ)"
            inputmode="numeric"
            placeholder="2500000"
          />
          <FormControl
            v-model="form.duration_text"
            label="Thời lượng"
            placeholder="2 tháng (16 buổi)"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.audience"
            type="select"
            label="Đối tượng"
            :options="AUDIENCES"
          />
          <div class="grid grid-cols-2 gap-4">
            <FormControl
              v-model="form.min_age"
              label="Tuổi từ"
              inputmode="numeric"
            />
            <FormControl
              v-model="form.max_age"
              label="đến"
              inputmode="numeric"
            />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <FormControl v-model="form.certificate" label="Chứng chỉ" />
          <FormControl
            v-model="form.offer"
            type="select"
            label="Mở lớp tại"
            :options="OFFERS"
          />
        </div>
        <FormControl
          v-model="form.aliases"
          label="Khách hay gọi là (cách nhau dấu phẩy)"
          placeholder="sql, hoc sql, phan tich du lieu"
        />
        <FormControl
          v-model="form.description"
          type="textarea"
          label="Tổng quan"
          :rows="3"
        />
        <FormControl
          v-model="form.syllabus"
          type="textarea"
          label="Nội dung học (mỗi dòng một phần)"
          :rows="4"
        />
        <div class="flex items-center justify-between">
          <div class="text-base-medium text-ink-gray-8">Câu hỏi thường gặp</div>
          <Button
            variant="ghost"
            label="Thêm câu hỏi"
            iconLeft="plus"
            @click="addFaq()"
          />
        </div>
        <div
          v-for="(faq, i) in form.faqs"
          :key="faq.id"
          class="flex flex-col gap-3 rounded border border-outline-gray-2 p-3"
        >
          <div class="flex items-center justify-between">
            <span class="text-base-medium text-ink-gray-8"
              >Câu hỏi {{ i + 1 }}</span
            >
            <Button
              variant="ghost"
              label="Xoá"
              @click="form.faqs.splice(i, 1)"
            />
          </div>
          <FormControl
            v-model="faq.question"
            placeholder="Học xong có làm được việc không?"
          />
          <FormControl
            v-model="faq.examples"
            type="textarea"
            label="Khách có thể hỏi kiểu (mỗi dòng một câu)"
            :rows="2"
          />
          <FormControl
            v-model="faq.answer"
            type="textarea"
            label="Bot trả lời"
            placeholder="Dạ học xong anh/chị …"
            :rows="3"
          />
        </div>
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button label="Huỷ" @click="show = false" />
        <Button
          variant="solid"
          label="Lưu khóa học"
          :loading="saving"
          @click="save"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { adminCall } from './adminApi'
import { Dialog, ErrorMessage, FormControl } from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'

// CRM Product.audience and offer options (mmm_custom.bot_admin.AUDIENCES / OFFERS)
const AUDIENCES = [
  { label: '—', value: '' },
  ...['Trẻ em', 'Học sinh – Sinh viên', 'Người đi làm', 'Doanh nghiệp'].map(
    (v) => ({ label: v, value: v }),
  ),
]
const OFFERS = [
  { label: 'Mọi chi nhánh', value: 'all' },
  { label: 'Chỉ chi nhánh lớn', value: 'full' },
]
const TEXT_FIELDS = [
  'product_name',
  'product_code',
  'button_label',
  'standard_rate',
  'duration_text',
  'min_age',
  'max_age',
  'certificate',
  'aliases',
]

const props = defineProps({
  course: { type: Object, default: () => ({}) },
  source: { type: String, default: '' },
})
const emit = defineEmits(['saved'])
const show = defineModel({ type: Boolean })

const lines = (value) => (Array.isArray(value) ? value.join('\n') : value || '')
// Imported files may carry the description as HTML paragraphs.
const plain = (html) =>
  new DOMParser()
    .parseFromString(html || '', 'text/html')
    .body.textContent.trim()
let faqId = 0

const c = props.course
const form = reactive({
  ...Object.fromEntries(
    TEXT_FIELDS.map((key) => [key, c[key] != null ? String(c[key]) : '']),
  ),
  course_group: c.course_group || '',
  audience: c.audience || '',
  offer: c.offer || 'all',
  description: /^\s*</.test(c.description || '')
    ? plain(String(c.description).replace(/<\/p>\s*<p>/g, '\n\n'))
    : c.description || '',
  syllabus: lines(c.syllabus),
  faqs: [],
})
;(c.faqs?.length ? c.faqs : [{}]).forEach((faq) => addFaq(faq))

const groups = ref([])
const groupOptions = computed(() => [
  { label: '— Chọn nhóm —', value: '' },
  ...groups.value.map((g) => ({ label: g, value: g })),
])
const error = ref('')
const saving = ref(false)

function addFaq(faq = {}) {
  form.faqs.push({
    id: ++faqId,
    question: faq.question || '',
    examples: lines(faq.examples),
    answer: faq.answer || '',
  })
}

async function save() {
  saving.value = true
  try {
    const course = {
      ...form,
      faqs: form.faqs.map(({ question, examples, answer }) => ({
        question,
        examples,
        answer,
      })),
      next_courses: c.next_courses || [],
    }
    const code = await adminCall('mmm_custom.bot_admin.save_course', { course })
    show.value = false
    emit('saved', code)
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    groups.value = (await adminCall('mmm_custom.bot_admin.course_groups')) || []
  } catch (e) {
    error.value = e.message
  }
})
</script>
