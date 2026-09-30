<template>
  <Dialog
    v-model:open="show"
    :title="schedule ? 'Sửa lớp khai giảng' : 'Thêm lớp khai giảng'"
    size="xl"
  >
    <template #default>
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.course"
            type="select"
            label="Khóa học"
            :options="courseOptions"
            :disabled="Boolean(schedule)"
          />
          <FormControl
            v-model="form.branch"
            type="select"
            label="Chi nhánh"
            :options="branchOptions"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.start_date"
            type="date"
            label="Ngày khai giảng"
            placeholder="Chọn ngày"
          />
          <FormControl
            v-model="form.shift"
            type="select"
            label="Ca học"
            :options="shiftOptions"
          />
        </div>
        <div class="grid grid-cols-3 gap-4">
          <FormControl
            v-model="form.weekdays"
            label="Lịch học"
            placeholder="T3, T5, T7"
          />
          <FormControl
            v-model="form.seats"
            type="number"
            label="Sĩ số (0 = không giới hạn)"
            :min="0"
          />
          <FormControl
            v-model="form.status"
            type="select"
            label="Trạng thái"
            :options="statusOptions"
          />
        </div>
        <ErrorMessage :message="error" />
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
import { adminCall } from '@/components/Admin/adminApi'
import { Dialog, ErrorMessage, FormControl } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  schedule: { type: Object, default: null },
  options: { type: Object, required: true },
  defaultBranch: { type: String, default: '' },
})
const emit = defineEmits(['saved'])
const show = defineModel({ type: Boolean })

const s = props.schedule
const form = reactive({
  course: s?.course || '',
  branch: s?.branch || props.defaultBranch || '',
  start_date: s ? String(s.start_date).slice(0, 10) : '',
  shift: s?.shift || props.options.shifts[0] || '',
  weekdays: s?.weekdays || '',
  seats: s?.seats ?? 0,
  status: s?.status || 'Open',
})
const pick = (label) => [{ label, value: '' }]
const courseOptions = computed(() => [
  ...pick('Chọn khóa học'),
  ...props.options.courses.map((c) => ({ label: c.name, value: c.code })),
])
const branchOptions = computed(() => [
  ...pick('Chọn chi nhánh'),
  ...props.options.branches.map((b) => ({ label: b, value: b })),
])
const shiftOptions = computed(() =>
  props.options.shifts.map((v) => ({ label: v, value: v })),
)
const STATUS_LABELS = {
  Open: 'Đang mở',
  Full: 'Đã đủ',
  Started: 'Đã khai giảng',
}
const statusOptions = computed(() =>
  props.options.statuses.map((v) => ({
    label: STATUS_LABELS[v] || v,
    value: v,
  })),
)
const error = ref('')
const saving = ref(false)

async function save() {
  saving.value = true
  try {
    await adminCall('mmm_custom.classes.save_schedule', {
      ...form,
      name: props.schedule?.name || '',
    })
    show.value = false
    emit('saved')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>
