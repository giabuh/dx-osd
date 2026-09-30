<template>
  <div class="flex flex-col gap-5 p-5">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h2 class="text-lg-semibold text-ink-gray-9">Kênh kết nối</h2>
        <p class="text-p-base text-ink-gray-6">
          Đăng nhập một lần để nhận tin nhắn từ nhiều Fanpage. Mỗi page thành
          một hộp thư trong Chatwoot, có bot tư vấn và nhân viên chi nhánh phụ
          trách.
        </p>
      </div>
      <Button
        label="Kiểm tra token"
        iconLeft="refresh-cw"
        :loading="checking"
        :disabled="!data.connections.length"
        @click="checkNow"
      />
    </div>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div
        v-for="p in data.providers"
        :key="p.key"
        class="flex flex-col gap-2 rounded-lg border border-outline-gray-2 p-4"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="text-base-medium text-ink-gray-9">{{ p.label }}</span>
          <Badge
            :label="
              p.status === 'live' ? `${p.connected} đã kết nối` : 'Sắp có'
            "
            :theme="p.status === 'live' ? 'blue' : 'gray'"
            variant="subtle"
          />
        </div>
        <p class="flex-1 text-p-sm text-ink-gray-6">{{ p.description }}</p>
        <div v-if="p.key === 'facebook'" class="flex flex-wrap gap-2">
          <Button
            variant="solid"
            label="Kết nối Facebook"
            iconLeft="log-in"
            :loading="starting"
            :disabled="!data.facebook.configured"
            @click="startFacebook"
          />
          <Button label="Dán token" @click="showToken = true" />
        </div>
      </div>
    </div>

    <div
      v-if="!data.facebook.configured || !data.facebook.chatwoot_configured"
      class="rounded-lg bg-surface-amber-1 p-4 text-p-base text-ink-amber-3"
    >
      <p v-if="!data.facebook.configured">
        Chưa cấu hình Facebook App: thêm <code>FB_APP_ID</code> và
        <code>FB_APP_SECRET</code> vào <code>.env</code> rồi chạy
        <code>scripts/configure-chatwoot.py</code>.
      </p>
      <p v-if="!data.facebook.chatwoot_configured">
        CRM chưa có token quản trị Chatwoot: chạy
        <code>scripts/configure-chatwoot.py</code>.
      </p>
    </div>
    <p class="text-p-sm text-ink-gray-5">
      Trong Meta App, mục Facebook Login → Valid OAuth Redirect URIs cần có:
      <code class="select-all">{{ data.facebook.redirect_uri }}</code>
    </p>

    <ErrorMessage :message="error" />
    <ListView
      :columns="columns"
      :rows="data.connections"
      row-key="name"
      :options="{
        selectable: false,
        emptyState: {
          title: 'Chưa kết nối page nào',
          description: 'Bấm “Kết nối Facebook” để chọn các Fanpage',
        },
      }"
    >
      <template #cell="{ item, column, row }">
        <div
          v-if="column.key === 'display_name'"
          class="flex min-w-0 items-center gap-2"
        >
          <img
            v-if="row.picture"
            :src="row.picture"
            class="size-6 rounded-full"
            alt=""
          />
          <div class="min-w-0">
            <div class="truncate text-base text-ink-gray-9">
              {{ item || row.external_id }}
            </div>
            <div class="truncate text-sm text-ink-gray-5">
              {{ row.provider }} · {{ row.external_id }}
            </div>
          </div>
        </div>
        <div
          v-else-if="column.key === 'status'"
          class="flex min-w-0 flex-col items-start"
        >
          <Badge
            :label="STATUS_LABELS[item] || item"
            :theme="STATUS_THEMES[item] || 'gray'"
            variant="subtle"
          />
          <span
            v-if="row.last_error"
            class="mt-0.5 truncate text-sm text-ink-red-4"
            :title="row.last_error"
          >
            {{ row.last_error }}
          </span>
        </div>
        <select
          v-else-if="column.key === 'branch'"
          :value="row.branch || ''"
          class="form-select w-full text-base"
          @click.stop
          @change="setBranch(row, $event.target.value)"
        >
          <option value="">Không gắn (bot giao từng khách)</option>
          <option v-for="b in data.branches" :key="b" :value="b">
            {{ b }}
          </option>
        </select>
        <div
          v-else-if="column.key === 'actions'"
          class="flex justify-end gap-1"
        >
          <Button
            v-if="row.chatwoot_url"
            variant="ghost"
            icon="external-link"
            title="Mở hộp thư trong Chatwoot"
            @click.stop="open(row.chatwoot_url)"
          />
          <Button
            v-if="row.status !== 'Connected'"
            variant="ghost"
            label="Kết nối lại"
            :disabled="!data.facebook.configured"
            @click.stop="startFacebook"
          />
          <Button
            v-if="row.status !== 'Disconnected'"
            variant="ghost"
            theme="red"
            label="Ngắt"
            @click.stop="disconnect(row)"
          />
        </div>
        <div v-else class="truncate text-base text-ink-gray-7">
          {{
            column.key === 'last_checked_at' ? displayTime(item) : (item ?? '—')
          }}
        </div>
      </template>
    </ListView>

    <FacebookPagesDialog
      v-if="picker"
      v-model="showPicker"
      :data="picker"
      :branches="data.branches"
      @connected="load"
    />
    <Dialog v-model:open="showToken" title="Dán access token Facebook">
      <template #default>
        <div class="flex flex-col gap-3">
          <p class="text-p-base text-ink-gray-6">
            Dùng khi CRM chưa có địa chỉ HTTPS công khai để Facebook chuyển về.
            Lấy User Access Token của tài khoản quản lý các page trong Graph API
            Explorer (chọn app của bạn và các quyền pages_show_list,
            pages_messaging, pages_manage_metadata, leads_retrieval).
          </p>
          <FormControl
            v-model="token"
            type="textarea"
            :rows="3"
            label="Token"
          />
          <ErrorMessage :message="tokenError" />
        </div>
      </template>
      <template #actions>
        <div class="flex justify-end gap-2">
          <Button label="Huỷ" @click="showToken = false" />
          <Button
            variant="solid"
            label="Lấy danh sách page"
            :loading="usingToken"
            @click="useToken"
          />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import FacebookPagesDialog from './FacebookPagesDialog.vue'
import { adminCall, displayTime } from './adminApi'
import { Badge, Dialog, ErrorMessage, FormControl, ListView } from 'frappe-ui'
import { onActivated, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const STATUS_LABELS = {
  Connected: 'Đang nhận tin',
  'Token expired': 'Token hết hạn',
  Disconnected: 'Đã ngắt',
  Error: 'Lỗi',
}
const STATUS_THEMES = {
  Connected: 'green',
  'Token expired': 'orange',
  Disconnected: 'gray',
  Error: 'red',
}

const route = useRoute()
const router = useRouter()
const data = ref({
  providers: [],
  connections: [],
  branches: [],
  facebook: { configured: true, chatwoot_configured: true, redirect_uri: '' },
})
const error = ref('')
const starting = ref(false)
const checking = ref(false)
const picker = ref(null)
const showPicker = ref(false)
const showToken = ref(false)
const token = ref('')
const tokenError = ref('')
const usingToken = ref(false)

const columns = [
  { label: 'Page', key: 'display_name', width: 2.4 },
  { label: 'Trạng thái', key: 'status', width: 1.6 },
  { label: 'Chi nhánh phụ trách', key: 'branch', width: 2 },
  { label: 'Form Lead Ads', key: 'lead_forms', width: 0.9 },
  { label: 'Kiểm tra lúc', key: 'last_checked_at', width: 1.2 },
  { label: '', key: 'actions', width: 1.6 },
]

async function load() {
  try {
    data.value = await adminCall('mmm_custom.channels.api.overview')
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

function openPicker(result) {
  picker.value = result
  showPicker.value = true
}

async function startFacebook() {
  starting.value = true
  try {
    const { url } = await adminCall('mmm_custom.channels.facebook.start')
    window.location.href = url
  } catch (e) {
    error.value = e.message
    starting.value = false
  }
}

async function useToken() {
  usingToken.value = true
  tokenError.value = ''
  try {
    const result = await adminCall('mmm_custom.channels.facebook.use_token', {
      access_token: token.value,
    })
    showToken.value = false
    token.value = ''
    openPicker(result)
  } catch (e) {
    tokenError.value = e.message
  } finally {
    usingToken.value = false
  }
}

async function setBranch(row, branch) {
  try {
    await adminCall('mmm_custom.channels.api.set_branch', {
      name: row.name,
      branch,
    })
    row.branch = branch
  } catch (e) {
    error.value = e.message
  }
}

async function disconnect(row) {
  const name = row.display_name || row.external_id
  if (
    !window.confirm(
      `Ngắt ${name}? Hệ thống ngừng nhận tin nhắn mới của page; hội thoại cũ vẫn còn trong Chatwoot.`,
    )
  )
    return
  try {
    await adminCall('mmm_custom.channels.facebook.disconnect', {
      name: row.name,
    })
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function checkNow() {
  checking.value = true
  try {
    await adminCall('mmm_custom.channels.facebook.check_now')
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    checking.value = false
  }
}

function open(url) {
  window.open(url, '_blank', 'noopener')
}

// Back from the Facebook login (mmm_custom.channels.facebook.callback).
async function handleReturn() {
  const { facebook, facebook_error: failed } = route.query
  if (!facebook && !failed) return
  router.replace({ query: {} })
  if (failed) {
    error.value = String(failed)
    return
  }
  try {
    openPicker(await adminCall('mmm_custom.channels.facebook.pages'))
  } catch (e) {
    error.value = e.message
  }
}

onActivated(async () => {
  await load()
  await handleReturn()
})
</script>
