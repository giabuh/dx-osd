<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Tri thức khóa học</h2>
        <p class="text-p-base text-ink-gray-6">
          Dữ liệu bot dùng để trả lời khách
        </p>
      </div>
      <div class="flex gap-2">
        <Button
          label="Nhập từ file"
          iconLeft="upload"
          @click="fileInput.click()"
        />
        <input
          ref="fileInput"
          type="file"
          accept=".json,application/json"
          class="hidden"
          @change="importFile"
        />
        <Button
          variant="solid"
          label="Thêm khóa học"
          iconLeft="plus"
          @click="openCourse({}, '')"
        />
      </div>
    </div>
    <div
      v-if="notice"
      class="rounded bg-surface-blue-2 px-3 py-2 text-p-base text-ink-blue-8"
    >
      {{ notice }}
    </div>
    <ErrorMessage :message="error" />
    <div class="grid grid-cols-1 gap-5 md:grid-cols-[minmax(260px,340px)_1fr]">
      <div
        class="flex flex-col gap-3 rounded shadow p-3 md:max-h-[70vh] md:overflow-y-auto"
      >
        <TextInput v-model="search" placeholder="Tìm khóa học">
          <template #prefix>
            <span
              class="lucide-search size-4 text-ink-gray-5"
              aria-hidden="true"
            />
          </template>
        </TextInput>
        <div v-if="loading" class="px-2 text-base text-ink-gray-5">
          Đang tải khóa học…
        </div>
        <div v-for="[group, rows] in grouped" :key="group">
          <div class="px-2 pb-1 pt-2 text-xs-medium uppercase text-ink-gray-5">
            {{ group || 'Khác' }}
          </div>
          <button
            v-for="course in rows"
            :key="course.code"
            class="w-full rounded px-2 py-2 text-left hover:bg-surface-gray-2"
            :class="course.code === selected ? 'bg-surface-gray-3' : ''"
            @click="showCourse(course.code)"
          >
            <div class="text-base text-ink-gray-9">{{ course.name }}</div>
            <div class="text-p-sm text-ink-gray-5">
              {{ course.faqs }} FAQ · {{ course.coverage }}% đầy đủ
            </div>
            <Progress
              class="mt-1.5"
              :value="clamp(course.coverage)"
              size="sm"
            />
          </button>
        </div>
        <div
          v-if="!loading && !grouped.length"
          class="px-2 text-base text-ink-gray-5"
        >
          Không tìm thấy khóa học.
        </div>
      </div>
      <div class="rounded shadow p-5">
        <div v-if="!detail && !detailError" class="text-base text-ink-gray-5">
          {{
            detailLoading
              ? 'Đang tải chi tiết…'
              : 'Chọn một khóa học để xem bot trả lời như thế nào.'
          }}
        </div>
        <ErrorMessage :message="detailError" />
        <div
          v-if="detail"
          ref="detailBox"
          class="flex flex-col gap-4 text-base text-ink-gray-8"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 class="text-lg-semibold text-ink-gray-9">
                {{ detail.name }}
              </h3>
              <div class="text-p-sm text-ink-gray-5">
                {{ detail.code }} · {{ detail.coverage }}% đầy đủ
              </div>
            </div>
            <Button
              label="Sửa dữ liệu khóa học"
              iconLeft="external-link"
              @click="openDesk(detail.code)"
            />
          </div>
          <section v-if="detail.gaps?.length">
            <h4 class="mb-1 text-base-medium">Cần bổ sung</h4>
            <ul class="list-disc pl-5 text-ink-red-6">
              <li v-for="gap in detail.gaps" :key="gap">{{ gap }}</li>
            </ul>
          </section>
          <section>
            <h4 class="mb-1 text-base-medium">Tổng quan</h4>
            <p class="whitespace-pre-wrap text-p-base">
              {{ detail.summary || 'Chưa có mô tả.' }}
            </p>
          </section>
          <p class="text-p-base">
            <span class="font-medium">Học phí:</span>{{ ' ' }}
            <template v-if="Number(detail.final_fee) < Number(detail.fee)">
              {{ money(detail.fee) }} →
              <span class="font-semibold">{{ money(detail.final_fee) }}</span>
              ({{ (detail.promotions || []).join(', ') }})
            </template>
            <template v-else>{{ money(detail.fee) }}</template>
            · <span class="font-medium">Thời lượng:</span>{{ ' ' }}
            {{ detail.duration || '—' }}
          </p>
          <section>
            <h4 class="mb-1 text-base-medium">Nội dung học</h4>
            <ul
              v-if="detail.syllabus?.length"
              class="list-disc pl-5 text-p-base"
            >
              <li v-for="(item, i) in detail.syllabus" :key="i">{{ item }}</li>
            </ul>
            <p v-else class="text-ink-gray-5">Chưa có dữ liệu.</p>
          </section>
          <section>
            <h4 class="mb-1 text-base-medium">Câu hỏi thường gặp</h4>
            <div
              v-for="(faq, i) in detail.faqs || []"
              :key="i"
              class="mb-3 border-l-2 border-outline-gray-2 pl-3"
            >
              <div class="text-base-medium">{{ faq.question }}</div>
              <p
                class="mt-1 whitespace-pre-wrap rounded bg-surface-gray-1 px-3 py-2 text-p-base"
                :class="faq.error ? 'text-ink-red-6' : ''"
              >
                {{ faq.error || faq.reply || 'Chưa có câu trả lời.' }}
              </p>
            </div>
            <p v-if="!detail.faqs?.length" class="text-ink-gray-5">
              Chưa có câu hỏi thường gặp.
            </p>
          </section>
          <section>
            <h4 class="mb-1 text-base-medium">
              Lớp sắp khai giảng ({{ detail.schedule_count || 0 }})
            </h4>
            <ul
              v-if="detail.schedules?.length"
              class="list-disc pl-5 text-p-base"
            >
              <li v-for="(row, i) in detail.schedules" :key="i">
                {{ row.weekday || '' }} {{ row.date || '' }} ·
                {{ row.shift || '' }} ·
                {{ row.branch || '' }}
              </li>
            </ul>
            <p v-else class="text-ink-gray-5">Chưa có dữ liệu.</p>
          </section>
        </div>
      </div>
    </div>
    <CourseDialog
      v-if="dialog.open"
      v-model="dialog.open"
      :course="dialog.course"
      :source="dialog.source"
      @saved="afterSave"
    />
  </div>
</template>

<script setup>
import CourseDialog from './CourseDialog.vue'
import { adminCall, money } from './adminApi'
import { ErrorMessage, Progress, TextInput } from 'frappe-ui'
import { computed, nextTick, onActivated, reactive, ref } from 'vue'

const courses = ref([])
const loaded = ref(false)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const search = ref('')
const selected = ref('')
const detail = ref(null)
const detailError = ref('')
const detailLoading = ref(false)
const detailBox = ref(null)
const fileInput = ref(null)
const dialog = reactive({ open: false, course: {}, source: '' })

const clamp = (value) => Math.max(0, Math.min(100, Number(value) || 0))

const grouped = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('vi')
  const groups = new Map()
  courses.value
    .filter((c) =>
      `${c.name} ${c.code} ${c.group}`.toLocaleLowerCase('vi').includes(query),
    )
    .forEach((c) => {
      if (!groups.has(c.group)) groups.set(c.group, [])
      groups.get(c.group).push(c)
    })
  return [...groups.entries()].sort(([a], [b]) =>
    (a || '').localeCompare(b || '', 'vi'),
  )
})

async function load() {
  loading.value = true
  try {
    courses.value =
      (await adminCall('mmm_custom.engine.knowledge.overview')) || []
    loaded.value = true
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function showCourse(code) {
  selected.value = code
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    detail.value = await adminCall('mmm_custom.engine.knowledge.course', {
      product: code,
    })
    await nextTick()
    if (window.matchMedia('(max-width: 767px)').matches) {
      detailBox.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  } catch (e) {
    detailError.value = e.message
  } finally {
    detailLoading.value = false
  }
}

function openDesk(code) {
  window.open(
    `/app/crm-product/${encodeURIComponent(code)}`,
    '_blank',
    'noopener',
  )
}

function openCourse(course, source) {
  error.value = ''
  Object.assign(dialog, { open: true, course, source })
}

async function importFile(event) {
  const file = event.target.files[0]
  event.target.value = '' // choosing the same file again still fires
  if (!file) return
  try {
    let data = JSON.parse(await file.text())
    if (Array.isArray(data)) {
      if (data.length !== 1) throw new Error('Mỗi file chứa một khóa học.')
      data = data[0]
    }
    if (!data || typeof data !== 'object')
      throw new Error('File không đúng mẫu khóa học.')
    openCourse(data, file.name)
  } catch (e) {
    const message =
      e instanceof SyntaxError ? 'File không phải JSON hợp lệ.' : e.message
    error.value = `${file.name}: ${message}`
  }
}

async function afterSave(code) {
  notice.value = `Đã thêm khóa ${code}. Bot trả lời được khóa này ngay.`
  search.value = ''
  await load()
  showCourse(code)
}

onActivated(() => loaded.value || load())
</script>
