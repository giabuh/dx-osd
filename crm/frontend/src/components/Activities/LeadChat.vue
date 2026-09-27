<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div
      class="flex items-center justify-between gap-2 px-3 pb-3 sm:px-10 text-p-sm text-ink-gray-5"
    >
      <span v-if="chat.data?.conversation">
        Cuộc chat #{{ chat.data.conversation }} · tự cập nhật mỗi 15 giây
      </span>
      <span v-else />
      <Button
        v-if="chat.data?.chatwoot_url"
        variant="ghost"
        label="Mở trong Chatwoot"
        iconLeft="external-link"
        @click="openChatwoot"
      />
    </div>
    <div
      ref="scroller"
      class="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-3 pb-4 sm:px-10"
    >
      <div
        v-if="chat.loading && !chat.data"
        class="flex flex-1 items-center justify-center gap-2 text-base text-ink-gray-5"
      >
        <LoadingIndicator class="size-4" /> Đang tải tin nhắn…
      </div>
      <ErrorMessage v-else-if="chat.error" :message="errorText(chat.error)" />
      <div
        v-else-if="chat.data && !chat.data.conversation"
        class="flex flex-1 flex-col items-center justify-center gap-1 text-center"
      >
        <span class="text-base-medium text-ink-gray-7">
          Khách này chưa nhắn tin qua Chatwoot
        </span>
        <span class="text-p-sm text-ink-gray-5">
          Lead đến từ nguồn khác (form quảng cáo, hotline, nhập tay) nên chưa có
          cuộc chat để trả lời
        </span>
      </div>
      <template v-for="m in messages" v-else :key="m.id">
        <div
          v-if="m.kind === 'activity'"
          class="self-center px-2 text-center text-p-xs text-ink-gray-5"
        >
          {{ m.text }} · {{ clock(m.at) }}
        </div>
        <div
          v-else
          class="flex max-w-[80%] flex-col gap-1"
          :class="m.kind === 'customer' ? 'self-start' : 'self-end items-end'"
        >
          <div
            class="whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-p-base"
            :class="BUBBLE[m.kind]"
          >
            <span v-if="m.kind === 'note'" class="text-p-xs font-medium">
              Ghi chú nội bộ ·
            </span>
            {{ m.text || (m.attachments ? '[Tệp đính kèm]' : '') }}
          </div>
          <div v-if="m.buttons.length" class="flex flex-wrap justify-end gap-1">
            <Badge
              v-for="b in m.buttons"
              :key="b"
              :label="b"
              theme="gray"
              variant="outline"
            />
          </div>
          <span class="px-1 text-p-xs text-ink-gray-5">
            {{ who(m) }} · {{ clock(m.at) }}
          </span>
        </div>
      </template>
    </div>
    <form
      v-if="chat.data?.conversation"
      class="flex items-end gap-2 border-t px-3 py-3 sm:px-10"
      @submit.prevent="send"
    >
      <template v-if="chat.data.can_reply">
        <Textarea
          v-model="text"
          class="flex-1"
          :rows="2"
          :maxlength="2000"
          placeholder="Trả lời khách qua Messenger… (Ctrl+Enter để gửi)"
          @keydown.ctrl.enter.prevent="send"
          @keydown.meta.enter.prevent="send"
        />
        <Button
          variant="solid"
          type="submit"
          label="Gửi"
          :loading="sending"
          :disabled="!text.trim()"
        />
      </template>
      <span v-else class="text-p-sm text-ink-gray-5">
        Tài khoản Chatwoot của bạn chưa sẵn sàng để trả lời. Nhờ quản trị chạy
        đồng bộ nhân viên.
      </span>
    </form>
    <ErrorMessage
      v-if="sendError"
      class="px-3 pb-2 sm:px-10"
      :message="sendError"
    />
  </div>
</template>

<script setup>
// A Lead's Chatwoot conversation, read and answered from the CRM (mmm_custom.lead_chat).
import {
  Badge,
  ErrorMessage,
  LoadingIndicator,
  Textarea,
  call,
  createResource,
} from 'frappe-ui'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({ lead: { type: String, required: true } })

const BUBBLE = {
  customer: 'bg-surface-gray-2 text-ink-gray-9',
  bot: 'bg-surface-blue-2 text-ink-gray-9',
  staff: 'bg-surface-gray-7 text-ink-white',
  note: 'bg-surface-amber-2 text-ink-gray-9',
}
const POLL_MS = 15000

const chat = createResource({
  url: 'mmm_custom.lead_chat.chat',
  params: { lead: props.lead },
  auto: true,
})
const messages = computed(() => chat.data?.messages || [])
const text = ref('')
const sending = ref(false)
const sendError = ref('')
const scroller = ref(null)
let timer = null

const errorText = (error) =>
  error?.messages?.[0] || error?.message || 'Không tải được tin nhắn.'

function clock(at) {
  if (!at) return ''
  const date = new Date(Number(at) * 1000)
  return date.toLocaleString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  })
}

function who(m) {
  if (m.kind === 'customer') return 'Khách'
  if (m.kind === 'bot') return m.sender || 'Bot'
  return m.sender || 'Nhân viên'
}

function openChatwoot() {
  window.open(chat.data.chatwoot_url, '_blank', 'noopener')
}

async function scrollToEnd() {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}

// Keep the reader where they are unless they were already at the bottom.
watch(
  () => messages.value.length,
  (count, before) => {
    const el = scroller.value
    const atBottom =
      !el || !before || el.scrollHeight - el.scrollTop - el.clientHeight < 80
    if (count && atBottom) scrollToEnd()
  },
)

async function send() {
  const content = text.value.trim()
  if (!content || sending.value) return
  sending.value = true
  sendError.value = ''
  try {
    const message = await call('mmm_custom.lead_chat.send', {
      lead: props.lead,
      text: content,
    })
    text.value = ''
    chat.setData({ ...chat.data, messages: [...messages.value, message] })
    scrollToEnd()
  } catch (error) {
    sendError.value = errorText(error)
  } finally {
    sending.value = false
  }
}

onMounted(() => {
  timer = setInterval(() => {
    if (!document.hidden && !chat.loading) chat.reload()
  }, POLL_MS)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
