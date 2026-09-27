<template>
  <Dialog
    v-model:open="show"
    :title="
      person ? `Sửa ${person.full_name || person.name}` : 'Thêm nhân viên'
    "
    size="xl"
  >
    <template #default>
      <div class="flex flex-col gap-4">
        <div class="grid grid-cols-2 gap-4">
          <FormControl v-model="form.full_name" label="Họ tên" />
          <FormControl
            v-model="form.email"
            type="email"
            label="Email đăng nhập"
            :disabled="Boolean(person)"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.branch"
            type="select"
            label="Chi nhánh"
            :options="branchOptions"
          />
          <FormControl
            v-model="form.level"
            type="select"
            label="Cấp bậc"
            :options="levelOptions"
          />
        </div>
        <div>
          <div class="mb-1.5 text-xs text-ink-gray-5">
            Chuyên môn (nhóm khóa học)
          </div>
          <div class="flex flex-wrap gap-x-5 gap-y-2">
            <FormControl
              v-for="group in data.groups"
              :key="group"
              type="checkbox"
              :label="group"
              :modelValue="form.specialties.includes(group)"
              @update:modelValue="(on) => toggle(group, on)"
            />
          </div>
        </div>
        <FormControl
          v-model="form.handles_b2b"
          type="checkbox"
          label="Chuyên khách doanh nghiệp (B2B)"
        />
        <FormControl
          v-model="form.active"
          type="checkbox"
          label="Đang làm việc (bot được giao khách)"
        />
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
import { adminCall, LEVEL_LABELS } from './adminApi'
import { Dialog, ErrorMessage, FormControl } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  person: { type: Object, default: null },
  data: { type: Object, required: true },
  defaultBranch: { type: String, default: '' },
})
const emit = defineEmits(['saved'])
const show = defineModel({ type: Boolean })

const form = reactive({
  full_name: props.person?.full_name || '',
  email: props.person?.name || '',
  branch: props.person ? props.person.branch || '' : props.defaultBranch,
  level: props.person?.level || 'Consultant',
  specialties: [...(props.person?.specialties || [])],
  handles_b2b: Boolean(props.person?.handles_b2b),
  active: props.person ? Boolean(props.person.active) : true,
})

const branchOptions = computed(() => [
  { label: 'Không thuộc chi nhánh (Tổng đài / B2B)', value: '' },
  ...props.data.branches.map((name) => ({ label: name, value: name })),
])
const levelOptions = computed(() =>
  props.data.levels.map((level) => ({
    label: LEVEL_LABELS[level] || level,
    value: level,
  })),
)
const error = ref('')
const saving = ref(false)

function toggle(group, on) {
  form.specialties = on
    ? [...form.specialties, group]
    : form.specialties.filter((item) => item !== group)
}

async function save() {
  saving.value = true
  try {
    await adminCall('mmm_custom.bot_admin.save_staff', {
      ...form,
      is_new: props.person ? '0' : '1',
      handles_b2b: form.handles_b2b ? 1 : 0,
      active: form.active ? 1 : 0,
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
