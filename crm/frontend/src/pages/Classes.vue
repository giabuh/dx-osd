<template>
  <LayoutHeader>
    <template #left-header>
      <Breadcrumbs :items="breadcrumbs" />
    </template>
  </LayoutHeader>
  <div class="flex h-full flex-col overflow-hidden">
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
import ClassSchedules from '@/components/Classes/ClassSchedules.vue'
import AdminKnowledge from '@/components/Admin/AdminKnowledge.vue'
import { adminCall } from '@/components/Admin/adminApi'
import { Breadcrumbs, Tabs, usePageMeta } from 'frappe-ui'
import { computed, markRaw, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// Courses are edited by managers only (the same screen as /crm/admin → Tri thức khóa học).
const canEditCourses = ref(false)
const tabs = computed(() => [
  {
    name: 'schedules',
    label: 'Lớp khai giảng',
    icon: 'lucide-calendar-days',
    component: markRaw(ClassSchedules),
  },
  ...(canEditCourses.value
    ? [
        {
          name: 'courses',
          label: 'Khóa học',
          icon: 'lucide-book-open',
          component: markRaw(AdminKnowledge),
        },
      ]
    : []),
])

const current = computed(() =>
  tabs.value.some((tab) => tab.name === route.params.tab)
    ? route.params.tab
    : 'schedules',
)
const activeTab = computed(() =>
  tabs.value.find((tab) => tab.name === current.value),
)
const tabIndex = computed({
  get: () => tabs.value.findIndex((tab) => tab.name === current.value),
  set: (index) =>
    router.push({ name: 'Classes', params: { tab: tabs.value[index].name } }),
})

const breadcrumbs = computed(() => [
  { label: 'Khóa học & Lớp', route: { name: 'Classes' } },
  {
    label: activeTab.value.label,
    route: { name: 'Classes', params: { tab: current.value } },
  },
])

onMounted(async () => {
  try {
    canEditCourses.value = Boolean(
      (await adminCall('mmm_custom.classes.context')).can_edit_courses,
    )
  } catch {
    canEditCourses.value = false
  }
})

usePageMeta(() => ({ title: `${activeTab.value.label} · Khóa học & Lớp` }))
</script>
