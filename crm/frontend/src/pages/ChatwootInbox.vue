<template>
  <div class="flex h-full w-full flex-col overflow-hidden bg-surface-white">
    <!-- Header Toolbar -->
    <header class="flex h-11 shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-white px-4">
      <div class="flex items-center gap-2 font-medium text-ink-gray-9">
        <MessageSquareIcon class="size-4 text-ink-gray-7" />
        <span class="text-sm font-semibold">Hộp Thư Chatwoot</span>
      </div>

      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          :iconLeft="RefreshIcon"
          label="Tải lại"
          @click="reloadIframe"
        />

        <Button
          variant="solid"
          size="sm"
          :iconLeft="ExternalLinkIcon"
          label="Mở tab riêng"
          @click="openExternalWindow"
        />
      </div>
    </header>

    <!-- Embedded Chatwoot Iframe -->
    <div class="relative flex-1 w-full overflow-hidden bg-surface-gray-1">
      <iframe
        ref="chatwootFrame"
        :src="chatwootUrl"
        class="h-full w-full border-0"
        allow="camera; microphone; clipboard-read; clipboard-write; fullscreen"
      ></iframe>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Button, toast } from 'frappe-ui'
import MessageSquareIcon from '~icons/lucide/message-square'
import RefreshIcon from '~icons/lucide/refresh-ccw'
import ExternalLinkIcon from '~icons/lucide/external-link'

const chatwootFrame = ref(null)

// Compute Chatwoot URL pointing to port 3000 on the current host
const chatwootUrl = computed(() => {
  const host = window.location.hostname || '127.0.0.1'
  return `http://${host}:3000/app`
})

function reloadIframe() {
  if (chatwootFrame.value) {
    chatwootFrame.value.src = chatwootUrl.value
    toast({
      title: 'Đang tải lại hộp thư Chatwoot...',
      icon: 'check',
    })
  }
}

function openExternalWindow() {
  window.open(chatwootUrl.value, '_blank')
}
</script>
