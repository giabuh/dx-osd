<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Thử chat với bot</h2>
        <p class="text-p-base text-ink-gray-6">
          Cuộc trò chuyện thử không gửi tin nhắn hoặc tạo Lead
        </p>
      </div>
      <Button
        label="Cuộc trò chuyện mới"
        iconLeft="refresh-ccw"
        @click="reset"
      />
    </div>
    <div class="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(320px,1fr)_360px]">
      <div class="flex flex-col rounded shadow p-4">
        <div class="flex items-center justify-between gap-2">
          <span class="text-p-base text-ink-gray-5"
            >Bạn đang đóng vai khách hàng</span
          >
          <FormControl v-model="useJev" type="checkbox" label="Dùng Jev" />
        </div>
        <div
          ref="log"
          class="flex h-[52vh] min-h-[300px] flex-col gap-2.5 overflow-y-auto py-3"
          aria-live="polite"
        >
          <template v-for="(item, i) in messages" :key="i">
            <div
              v-if="item.role !== 'chips'"
              class="max-w-[84%] whitespace-pre-wrap rounded-lg px-3 py-2 text-p-base"
              :class="
                item.role === 'customer'
                  ? 'self-end bg-surface-gray-7 text-ink-white'
                  : 'self-start bg-surface-gray-2 text-ink-gray-8'
              "
            >
              {{ item.text }}
            </div>
            <div
              v-else-if="i === messages.length - 1"
              class="flex flex-wrap gap-2"
            >
              <Button
                v-for="title in item.buttons"
                :key="title"
                :label="title"
                @click="send(title)"
              />
            </div>
          </template>
        </div>
        <form class="flex gap-2 border-t pt-3" @submit.prevent="submit">
          <TextInput
            ref="input"
            v-model="text"
            class="flex-1"
            placeholder="Nhập tin nhắn của khách hàng…"
            :maxlength="1000"
            autocomplete="off"
          />
          <Button
            variant="solid"
            label="Gửi"
            type="submit"
            :loading="sending"
          />
        </form>
      </div>
      <div class="flex flex-col gap-3 rounded shadow p-4">
        <div class="text-base-medium text-ink-gray-8">Bot hiểu gì</div>
        <p class="text-p-base text-ink-gray-5">
          Gửi tin nhắn để xem từ khóa, Jev và lý do bot trả lời.
        </p>
        <template v-if="inspector">
          <p class="text-p-base">
            <span class="font-medium">Lý do:</span> {{ inspector.reason }}
          </p>
          <div class="text-sm-medium text-ink-gray-7">Từ khóa khớp</div>
          <pre
            class="max-h-44 overflow-auto whitespace-pre-wrap break-all rounded bg-surface-gray-1 p-2 text-xs"
            >{{ inspector.matches }}</pre
          >
          <div class="text-sm-medium text-ink-gray-7">Câu trả lời từ Jev</div>
          <pre
            class="max-h-44 overflow-auto whitespace-pre-wrap break-all rounded bg-surface-gray-1 p-2 text-xs"
            >{{ inspector.jev }}</pre
          >
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { adminCall } from './adminApi'
import { FormControl, TextInput } from 'frappe-ui'
import { nextTick, ref } from 'vue'

const newSession = () =>
  window.crypto?.randomUUID?.() ||
  `${Date.now()}-${Math.random().toString(36).slice(2)}`

let session = newSession()
const messages = ref([]) // { role: customer | bot | chips, text?, buttons? }
const inspector = ref(null)
const text = ref('')
const useJev = ref(false)
const sending = ref(false)
const log = ref(null)
const input = ref(null)

async function push(item) {
  messages.value.push(item)
  await nextTick()
  if (log.value) log.value.scrollTop = log.value.scrollHeight
}

async function send(message) {
  if (sending.value || !message.trim()) return
  sending.value = true
  messages.value = messages.value.filter((item) => item.role !== 'chips')
  push({ role: 'customer', text: message })
  try {
    const result = await adminCall('mmm_custom.engine.playground.simulate', {
      session,
      text: message,
      jev: useJev.value ? 1 : 0,
    })
    if (!result?.duplicate) {
      for (const reply of result.reply?.messages || [])
        push({ role: 'bot', text: reply })
      const buttons = result.reply?.buttons || []
      if (buttons.length) push({ role: 'chips', buttons })
      inspector.value = {
        reason: result.decision?.reason || '—',
        matches: JSON.stringify(result.understanding?.matches || [], null, 2),
        jev: JSON.stringify(result.jev || {}, null, 2),
      }
    }
  } catch (e) {
    push({ role: 'bot', text: `Lỗi: ${e.message}` })
  } finally {
    sending.value = false
    input.value?.el?.focus?.()
  }
}

function submit() {
  const message = text.value.trim()
  text.value = ''
  send(message)
}

async function reset() {
  try {
    await adminCall('mmm_custom.engine.playground.reset', { session })
    session = newSession()
    messages.value = []
    inspector.value = null
  } catch (e) {
    push({ role: 'bot', text: `Lỗi: ${e.message}` })
  }
}
</script>
