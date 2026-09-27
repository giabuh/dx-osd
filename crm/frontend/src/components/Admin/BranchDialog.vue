<template>
  <Dialog
    v-model:open="show"
    :title="branch ? `Sửa ${branch.name}` : 'Thêm chi nhánh'"
    size="xl"
  >
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl
          v-model="form.territory_name"
          label="Tên chi nhánh"
          placeholder="CN Dĩ An"
          :disabled="Boolean(branch)"
        />
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.area"
            type="select"
            label="Khu vực"
            :options="areaOptions"
          />
          <FormControl
            v-if="form.area === NEW_AREA"
            v-model="form.new_area"
            label="Tên khu vực mới"
            placeholder="Bình Dương"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <FormControl
            v-model="form.button_label"
            label="Chữ trên nút bot"
            placeholder="Dĩ An"
            :maxlength="20"
          />
          <FormControl
            v-model="form.branch_code"
            label="Mã chi nhánh"
            placeholder="BD-DA"
          />
        </div>
        <FormControl
          v-model="form.address"
          type="textarea"
          label="Địa chỉ"
          :rows="2"
        />
        <div class="grid grid-cols-2 gap-4">
          <FormControl v-model="form.hotline" label="Hotline" />
          <FormControl v-model="form.map_url" label="Link Google Maps" />
        </div>
        <FormControl
          v-model="form.aliases"
          label="Khách hay gọi là (cách nhau dấu phẩy)"
          placeholder="Dĩ An, Di An"
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
import { adminCall } from './adminApi'
import { Dialog, ErrorMessage, FormControl } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'

const NEW_AREA = '__new'
const FIELDS = [
  'button_label',
  'branch_code',
  'address',
  'hotline',
  'map_url',
  'aliases',
]

const props = defineProps({
  branch: { type: Object, default: null },
  areas: { type: Array, default: () => [] },
})
const emit = defineEmits(['saved'])
const show = defineModel({ type: Boolean })

const form = reactive({
  territory_name: props.branch?.name || '',
  area: props.branch?.area || props.areas[0] || NEW_AREA,
  new_area: '',
  ...Object.fromEntries(FIELDS.map((key) => [key, props.branch?.[key] || ''])),
})
const areaOptions = computed(() => [
  ...props.areas.map((area) => ({ label: area, value: area })),
  { label: '+ Khu vực mới…', value: NEW_AREA },
])
const error = ref('')
const saving = ref(false)

async function save() {
  const isNew = form.area === NEW_AREA
  saving.value = true
  try {
    await adminCall('mmm_custom.bot_admin.save_branch', {
      ...form,
      name: props.branch?.name || '',
      area: isNew ? '' : form.area,
      new_area: isNew ? form.new_area : '',
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
