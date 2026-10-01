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
    <div class="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(320px,1fr)_380px]">
      <div class="flex flex-col gap-3 rounded shadow p-4">
        <div
          v-if="scripts.length"
          class="flex flex-wrap items-center gap-2 rounded border border-dashed border-outline-gray-2 bg-surface-gray-1 p-2.5"
        >
          <span class="text-sm-medium text-ink-gray-6">Kịch bản mẫu</span>
          <Button
            v-for="script in scripts"
            :key="script.id"
            :label="script.title"
            iconLeft="play"
            :variant="playing === script.id ? 'solid' : 'outline'"
            :disabled="!!playing && playing !== script.id"
            @click="play(script)"
          />
          <Button
            v-if="playing"
            label="Dừng"
            theme="red"
            variant="ghost"
            @click="stop"
          />
        </div>
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
          <p
            v-if="!messages.length"
            class="m-auto max-w-xs text-center text-p-base text-ink-gray-5"
          >
            Bấm một kịch bản mẫu ở trên hoặc nhập tin nhắn để bắt đầu.
          </p>
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
                :disabled="!!playing"
                @click="send(title)"
              />
            </div>
          </template>
          <div
            v-if="sending"
            class="self-start rounded-lg bg-surface-gray-2 px-3 py-2 text-p-base text-ink-gray-5"
          >
            Bot đang trả lời…
          </div>
        </div>
        <form class="flex gap-2 border-t pt-3" @submit.prevent="submit">
          <TextInput
            ref="input"
            v-model="text"
            class="flex-1"
            placeholder="Nhập tin nhắn của khách hàng…"
            :maxlength="1000"
            autocomplete="off"
            :disabled="!!playing"
          />
          <Button
            variant="solid"
            label="Gửi"
            type="submit"
            :loading="sending"
            :disabled="!!playing"
          />
        </form>
      </div>

      <div class="flex flex-col gap-4 rounded shadow p-4">
        <div class="text-base-medium text-ink-gray-8">Bot hiểu gì</div>
        <p v-if="!inspector" class="text-p-base text-ink-gray-5">
          Gửi tin nhắn để xem bot hiểu gì, quyết định gì và sẽ ghi gì vào CRM.
        </p>
        <template v-else>
          <div class="grid grid-cols-2 gap-2.5">
            <div
              class="flex flex-col gap-1 rounded bg-surface-gray-1 px-3 py-2"
            >
              <span class="text-xs uppercase tracking-wide text-ink-gray-5"
                >Khách muốn</span
              >
              <span class="text-base-medium text-ink-gray-9">{{
                inspector.wants
              }}</span>
            </div>
            <div
              class="flex flex-col gap-1 rounded bg-surface-gray-1 px-3 py-2"
            >
              <span class="text-xs uppercase tracking-wide text-ink-gray-5"
                >Độ nóng</span
              >
              <span class="flex items-center gap-1.5">
                <Badge
                  v-if="inspector.heat"
                  :label="inspector.heat.label"
                  :theme="inspector.heat.theme"
                  size="md"
                />
                <span v-else class="text-p-sm text-ink-gray-5"
                  >Chưa rõ (cần Jev)</span
                >
              </span>
            </div>
          </div>

          <div class="flex flex-col gap-1.5">
            <span class="text-xs uppercase tracking-wide text-ink-gray-5"
              >Bot quyết định</span
            >
            <div
              class="flex flex-col gap-1.5 rounded border border-outline-gray-1 p-3"
            >
              <Badge
                class="self-start"
                :label="inspector.decision"
                :theme="DECISION_THEME[inspector.type] || 'gray'"
                size="md"
              />
              <p class="text-p-base text-ink-gray-7">{{ inspector.reason }}</p>
            </div>
          </div>

          <div class="flex flex-col gap-1.5">
            <span class="text-xs uppercase tracking-wide text-ink-gray-5"
              >Thông tin đã nắm</span
            >
            <div class="overflow-hidden rounded border border-outline-gray-1">
              <div
                v-for="fact in inspector.facts"
                :key="fact.key"
                class="grid grid-cols-[18px_110px_minmax(0,1fr)_auto] items-center gap-2 border-t border-outline-gray-1 px-3 py-1.5 text-p-sm first:border-t-0"
                :class="fact.new ? 'bg-surface-green-1' : ''"
              >
                <FeatherIcon
                  :name="fact.value ? 'check-circle' : 'circle'"
                  class="size-4"
                  :class="fact.value ? 'text-ink-green-3' : 'text-ink-gray-4'"
                />
                <span class="text-ink-gray-6">{{ fact.label }}</span>
                <span
                  class="break-words"
                  :class="
                    fact.value
                      ? 'font-medium text-ink-gray-9'
                      : 'text-ink-gray-4'
                  "
                  >{{ fact.value || 'chưa có' }}</span
                >
                <Badge v-if="fact.new" label="mới" theme="green" />
                <span v-else />
              </div>
            </div>
          </div>

          <div class="flex flex-col gap-1.5">
            <span class="text-xs uppercase tracking-wide text-ink-gray-5"
              >Bot dựa vào</span
            >
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="source in inspector.sources"
                :key="source"
                class="rounded bg-surface-gray-2 px-2 py-0.5 text-p-sm text-ink-gray-7"
                >{{ source }}</span
              >
            </div>
          </div>

          <div class="flex flex-col gap-1.5">
            <span class="text-xs uppercase tracking-wide text-ink-gray-5"
              >Khi chạy thật sẽ</span
            >
            <ul
              v-if="inspector.actions.length"
              class="flex list-disc flex-col gap-1 pl-5 text-p-base text-ink-gray-7"
            >
              <li v-for="action in inspector.actions" :key="action">
                {{ action }}
              </li>
            </ul>
            <p v-else class="text-p-sm text-ink-gray-5">
              Chỉ trả lời, chưa ghi gì vào CRM.
            </p>
          </div>

          <details class="border-t border-outline-gray-1 pt-3">
            <summary class="cursor-pointer text-p-sm text-ink-gray-6">
              Chi tiết kỹ thuật (JSON)
            </summary>
            <div class="mt-2 flex flex-col gap-2">
              <div class="text-sm-medium text-ink-gray-7">Từ khóa khớp</div>
              <pre
                class="max-h-44 overflow-auto whitespace-pre-wrap break-all rounded bg-surface-gray-1 p-2 text-xs"
                >{{ inspector.matches }}</pre
              >
              <div class="text-sm-medium text-ink-gray-7">
                Câu trả lời từ Jev
              </div>
              <pre
                class="max-h-44 overflow-auto whitespace-pre-wrap break-all rounded bg-surface-gray-1 p-2 text-xs"
                >{{ inspector.jev }}</pre
              >
            </div>
          </details>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { adminCall } from './adminApi'
import { Badge, FeatherIcon, FormControl, TextInput } from 'frappe-ui'
import { nextTick, onMounted, ref } from 'vue'

const DECISION_THEME = {
  answer: 'blue',
  ask_slot: 'orange',
  confirm: 'orange',
  handoff: 'green',
  silent: 'gray',
}
const HEAT = {
  hot: { label: 'Nóng', theme: 'red' },
  warm: { label: 'Ấm', theme: 'orange' },
  cold: { label: 'Lạnh', theme: 'blue' },
}
const INTENTS = {
  purchase: 'Muốn đăng ký',
  price_inquiry: 'Hỏi giá, lịch học',
  support: 'Cần hỗ trợ',
  complaint: 'Phàn nàn',
  spam: 'Tin rác',
  other: 'Khác',
}
const STEP_MS = 1000 // pause between the messages of a sample chat

const newSession = () =>
  window.crypto?.randomUUID?.() ||
  `${Date.now()}-${Math.random().toString(36).slice(2)}`
let session = newSession()
let run = 0 // bumped to stop a sample chat that is playing

const messages = ref([]) // { role: customer | bot | chips, text?, buttons? }
const inspector = ref(null)
const text = ref('')
const useJev = ref(false)
const sending = ref(false)
const scripts = ref([])
const playing = ref('')
const log = ref(null)
const input = ref(null)

onMounted(async () => {
  try {
    scripts.value = await adminCall('mmm_custom.engine.playground.demo_scripts')
  } catch {
    scripts.value = [] // the chat still works without sample chats
  }
})

async function scrollDown() {
  await nextTick()
  if (log.value) log.value.scrollTop = log.value.scrollHeight
}

function push(item) {
  messages.value.push(item)
  scrollDown()
}

function view(result) {
  const summary = result.summary || {}
  const u = result.understanding || {}
  const jev = result.jev || {}
  const intent = INTENTS[u.intent?.value]
  const sources = [
    ...(summary.tapped ? ['Khách bấm nút'] : []),
    ...(summary.keywords || []).map((name) => `Từ khóa: ${name}`),
    jev.status === 'ok' ? 'Jev: đã hỏi' : 'Jev: không dùng',
  ]
  return {
    wants: summary.skills?.length ? summary.skills.join(', ') : intent || '—',
    heat: HEAT[u.hotness?.value] || null,
    type: result.decision?.type,
    decision: summary.decision || result.decision?.type || '—',
    reason: result.decision?.reason || '—',
    facts: summary.facts || [],
    sources,
    actions: summary.actions || [],
    matches: JSON.stringify(u.matches || [], null, 2),
    jev: JSON.stringify(jev, null, 2),
  }
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
      inspector.value = view(result)
    }
  } catch (e) {
    push({ role: 'bot', text: `Lỗi: ${e.message}` })
  } finally {
    sending.value = false
    scrollDown()
    if (!playing.value) input.value?.el?.focus?.()
  }
}

function submit() {
  const message = text.value.trim()
  text.value = ''
  send(message)
}

async function reset() {
  stop()
  try {
    await adminCall('mmm_custom.engine.playground.reset', { session })
    session = newSession()
    messages.value = []
    inspector.value = null
  } catch (e) {
    push({ role: 'bot', text: `Lỗi: ${e.message}` })
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// A sample chat: each message is sent in turn; {tap: n} taps the n-th button of the bot's last
// reply and is skipped when the reply had no such button (the live classes decide the buttons).
async function play(script) {
  if (playing.value) return
  await reset()
  const id = ++run
  playing.value = script.id
  try {
    for (const step of script.messages || []) {
      let message = step
      if (typeof step === 'object') {
        const last = messages.value[messages.value.length - 1]
        message = last?.role === 'chips' ? last.buttons[step.tap] : ''
      }
      if (!message) continue
      await send(message)
      if (id !== run) return
      await sleep(STEP_MS)
      if (id !== run) return
    }
  } finally {
    if (id === run) playing.value = ''
  }
}

function stop() {
  run++
  playing.value = ''
}
</script>
