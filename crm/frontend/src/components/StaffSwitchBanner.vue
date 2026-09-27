<template>
  <div
    v-if="staffSwitch.data?.impersonated_by"
    class="flex shrink-0 flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-surface-amber-2 px-4 py-1.5 text-p-sm text-ink-amber-8"
  >
    <span>
      Đang xem CRM với tư cách
      <b>{{ staffSwitch.data.full_name || staffSwitch.data.user }}</b>
      (demo, mở bởi {{ staffSwitch.data.impersonated_by }})
    </span>
    <Button
      size="sm"
      label="Quay lại tài khoản quản trị"
      :loading="leaving"
      @click="leave"
    />
    <span v-if="error" class="text-ink-red-6">{{ error }}</span>
  </div>
</template>

<script setup>
import { staffSwitch, switchBack } from '@/composables/staffSwitch'
import { ref } from 'vue'

const leaving = ref(false)
const error = ref('')

async function leave() {
  leaving.value = true
  try {
    await switchBack()
  } catch (e) {
    error.value = e.message
    leaving.value = false
  }
}
</script>
