<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Kiểm tra kịch bản</h2>
        <p class="text-p-base text-ink-gray-6">
          Chạy thử các tình huống khách nhắn tin trên dữ liệu thật (không gửi
          tin, không tạo Lead) để chắc bot phân khách đúng người
        </p>
      </div>
      <Button
        variant="solid"
        label="Chạy kiểm tra"
        iconLeft="play"
        :loading="running"
        @click="run"
      />
    </div>
    <ErrorMessage :message="error" />
    <div
      v-if="result"
      class="flex items-center gap-3 rounded px-4 py-3"
      :class="allPassed ? 'bg-surface-green-2' : 'bg-surface-amber-2'"
    >
      <span
        class="size-5"
        :class="
          allPassed
            ? 'lucide-circle-check text-ink-green-8'
            : 'lucide-triangle-alert text-ink-amber-8'
        "
        aria-hidden="true"
      />
      <span class="text-base-medium text-ink-gray-9">
        {{ result.passed }}/{{ result.total }} kịch bản đạt
      </span>
    </div>
    <div v-else-if="!running" class="text-p-base text-ink-gray-5">
      Bấm “Chạy kiểm tra” để bắt đầu.
    </div>
    <div class="flex flex-col gap-3">
      <div
        v-for="item in result?.results || []"
        :key="item.id"
        class="rounded shadow"
      >
        <button
          class="flex w-full items-start gap-3 px-4 py-3 text-left"
          @click="open[item.id] = !open[item.id]"
        >
          <Badge
            :label="item.passed ? 'Đạt' : 'Chưa đạt'"
            :theme="item.passed ? 'green' : 'red'"
          />
          <div class="flex min-w-0 flex-1 flex-col">
            <span class="text-base-medium text-ink-gray-9">
              {{ item.id }} · {{ item.title }}
            </span>
            <span class="text-p-sm text-ink-gray-5">{{ item.why }}</span>
          </div>
          <span
            v-if="item.assigned"
            class="hidden text-p-sm text-ink-gray-6 sm:block"
          >
            → {{ item.assigned.team }}
          </span>
          <span
            class="size-4 text-ink-gray-5"
            :class="open[item.id] ? 'lucide-chevron-up' : 'lucide-chevron-down'"
            aria-hidden="true"
          />
        </button>
        <div
          v-if="open[item.id]"
          class="grid grid-cols-1 gap-4 border-t border-outline-gray-1 p-4 lg:grid-cols-2"
        >
          <div class="flex flex-col gap-2">
            <div class="text-xs-medium uppercase text-ink-gray-5">
              Hội thoại
            </div>
            <div
              v-for="(turn, index) in item.transcript"
              :key="index"
              class="flex flex-col gap-1"
            >
              <div
                class="self-end rounded bg-surface-blue-2 px-3 py-1.5 text-p-base text-ink-gray-9"
              >
                {{ turn.customer }}
              </div>
              <div
                v-for="(line, i) in turn.bot"
                :key="i"
                class="self-start whitespace-pre-line rounded bg-surface-gray-2 px-3 py-1.5 text-p-base text-ink-gray-8"
              >
                {{ line }}
              </div>
              <div v-if="turn.reason" class="text-p-sm text-ink-gray-5">
                {{ turn.reason }}
              </div>
            </div>
          </div>
          <div class="flex flex-col gap-2">
            <div class="text-xs-medium uppercase text-ink-gray-5">Kiểm tra</div>
            <div
              v-for="(check, i) in item.checks"
              :key="i"
              class="flex items-start gap-2 text-p-base"
            >
              <span
                class="mt-0.5 size-4 shrink-0"
                :class="
                  check.ok
                    ? 'lucide-check text-ink-green-7'
                    : 'lucide-x text-ink-red-7'
                "
                aria-hidden="true"
              />
              <div class="flex flex-col">
                <span class="text-ink-gray-8">{{ check.check }}</span>
                <span v-if="!check.ok" class="text-p-sm text-ink-gray-5">
                  Mong đợi {{ show(check.expected) }} · thực tế
                  {{ show(check.actual) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { adminCall } from './adminApi'
import { Badge, Button, ErrorMessage } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'

const result = ref(null)
const running = ref(false)
const error = ref('')
const open = reactive({})

const allPassed = computed(
  () => result.value && result.value.passed === result.value.total,
)

const show = (value) =>
  value === true ? 'có' : value === false ? 'không' : value || '(trống)'

async function run() {
  running.value = true
  try {
    result.value = await adminCall('mmm_custom.engine.scenarios.run_all')
    for (const item of result.value.results) open[item.id] = !item.passed
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    running.value = false
  }
}
</script>
