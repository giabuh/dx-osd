<template>
  <LayoutHeader>
    <template #left-header>
      <Breadcrumbs :items="breadcrumbs" />
    </template>
    <template #right-header>
      <Button
        v-if="links.chatwoot_url"
        :label="'Mở Chatwoot'"
        iconLeft="external-link"
        @click="openExternal(links.chatwoot_url)"
      />
      <Button
        :label="'Quản trị nâng cao'"
        iconLeft="settings"
        @click="openExternal('/app/bot-sao-việt')"
      />
    </template>
  </LayoutHeader>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Same tab bar as the Lead page; the panels stay mounted (KeepAlive) so a
         playground conversation survives switching tabs. -->
    <Tabs
      v-model="tabIndex"
      :tabs="tabs"
      class="!flex-none [&_[role='tab']]:px-0 [&_[role='tab']]:shrink-0 [&_[role='tablist']]:px-5 [&_[role='tablist']::-webkit-scrollbar]:h-0 [&_[role='tablist']]:min-h-[45px] [&_[role='tablist']]:gap-7.5"
    />
    <div class="flex-1 overflow-y-auto">
      <KeepAlive>
        <component :is="activeTab.component" :key="current" />
      </KeepAlive>
    </div>
  </div>
</template>

<script setup>
import LayoutHeader from '@/components/LayoutHeader.vue'
import AdminOverview from '@/components/Admin/AdminOverview.vue'
import AdminCustomers from '@/components/Admin/AdminCustomers.vue'
import AdminScenarios from '@/components/Admin/AdminScenarios.vue'
import AdminBranches from '@/components/Admin/AdminBranches.vue'
import AdminStaff from '@/components/Admin/AdminStaff.vue'
import AdminKnowledge from '@/components/Admin/AdminKnowledge.vue'
import AdminPlayground from '@/components/Admin/AdminPlayground.vue'
import AdminQuizzes from '@/components/Admin/AdminQuizzes.vue'
import AdminChannels from '@/components/Admin/AdminChannels.vue'
import AdminTasks from '@/components/Admin/AdminTasks.vue'
import { adminCall } from '@/components/Admin/adminApi'
import { Breadcrumbs, Tabs, usePageMeta } from 'frappe-ui'
import { computed, markRaw, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  {
    name: 'overview',
    label: 'Tổng quan',
    icon: 'lucide-chart-column',
    component: markRaw(AdminOverview),
  },
  {
    name: 'customers',
    label: 'Khách hàng',
    icon: 'lucide-users-round',
    component: markRaw(AdminCustomers),
  },
  {
    name: 'tasks',
    label: 'Giao việc',
    icon: 'lucide-list-todo',
    component: markRaw(AdminTasks),
  },
  {
    name: 'branches',
    label: 'Chi nhánh',
    icon: 'lucide-map-pin',
    component: markRaw(AdminBranches),
  },
  {
    name: 'staff',
    label: 'Nhân viên',
    icon: 'lucide-users',
    component: markRaw(AdminStaff),
  },
  {
    name: 'channels',
    label: 'Kênh kết nối',
    icon: 'lucide-plug',
    component: markRaw(AdminChannels),
  },
  {
    name: 'knowledge',
    label: 'Tri thức khóa học',
    icon: 'lucide-book-open',
    component: markRaw(AdminKnowledge),
  },
  {
    name: 'quizzes',
    label: 'Bài test',
    icon: 'lucide-clipboard-check',
    component: markRaw(AdminQuizzes),
  },
  {
    name: 'playground',
    label: 'Thử chat với bot',
    icon: 'lucide-message-circle',
    component: markRaw(AdminPlayground),
  },
  {
    name: 'scenarios',
    label: 'Kiểm tra kịch bản',
    icon: 'lucide-list-checks',
    component: markRaw(AdminScenarios),
  },
]

const current = computed(() =>
  tabs.some((tab) => tab.name === route.params.tab)
    ? route.params.tab
    : 'overview',
)
const activeTab = computed(() => tabs.find((tab) => tab.name === current.value))
const tabIndex = computed({
  get: () => tabs.findIndex((tab) => tab.name === current.value),
  set: (index) =>
    router.push({ name: 'Admin', params: { tab: tabs[index].name } }),
})

const breadcrumbs = computed(() => [
  { label: 'Quản trị', route: { name: 'Admin' } },
  {
    label: activeTab.value.label,
    route: { name: 'Admin', params: { tab: current.value } },
  },
])

const links = ref({})

function openExternal(url) {
  window.open(url, '_blank', 'noopener')
}

onMounted(async () => {
  // Old /admin#branches links arrive here as /crm/admin#branches.
  const legacy = route.hash.slice(1)
  if (!route.params.tab && tabs.some((tab) => tab.name === legacy)) {
    router.replace({ name: 'Admin', params: { tab: legacy } })
  }
  try {
    links.value = (await adminCall('mmm_custom.bot_admin.app_links')) || {}
  } catch {
    links.value = {}
  }
})

usePageMeta(() => ({ title: `${activeTab.value.label} · Quản trị` }))
</script>
