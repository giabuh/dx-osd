<script setup>
// DX-OSD staff assist (D-111/D-112): the bot's countdown and the claim / reply-now / hand-back actions.
// Reads the custom attributes mmm_custom writes on the conversation: bot_mode, bot_fallback_at, claimed_by.
import { computed } from 'vue';
import { useStore } from 'vuex';
import { useI18n } from 'vue-i18n';
import { useNow } from '@vueuse/core';
import { useMapGetter } from 'dashboard/composables/store';
import { useAlert } from 'dashboard/composables';
import NextBanner from 'dashboard/components-next/banner/Banner.vue';
import NextButton from 'dashboard/components-next/button/Button.vue';

const store = useStore();
const { t } = useI18n();
const now = useNow({ interval: 15000 });

const currentChat = useMapGetter('getSelectedChat');
const currentUser = useMapGetter('getCurrentUser');
const agents = useMapGetter('agents/getAgents');

const attributes = computed(() => currentChat.value?.custom_attributes || {});
const dueAt = computed(() =>
  attributes.value.bot_fallback_at
    ? new Date(attributes.value.bot_fallback_at)
    : null
);
const claimedBy = computed(() => String(attributes.value.claimed_by || ''));
const isMine = computed(() => claimedBy.value === String(currentUser.value?.id));
const isCounting = computed(
  () => attributes.value.bot_mode === 'assist' && Boolean(dueAt.value)
);
const minutesLeft = computed(() =>
  Math.max(Math.ceil((dueAt.value - now.value) / 60000), 0)
);
const claimerName = computed(() => {
  if (isMine.value) return currentUser.value?.name;
  const agent = agents.value.find(a => String(a.id) === claimedBy.value);
  return agent?.name || t('CONVERSATION.BOT_ASSIST.SOMEONE');
});
const message = computed(() => {
  if (!isCounting.value) {
    return t('CONVERSATION.BOT_ASSIST.CLAIMED', { name: claimerName.value });
  }
  if (minutesLeft.value === 0) return t('CONVERSATION.BOT_ASSIST.DUE_NOW');
  return t('CONVERSATION.BOT_ASSIST.COUNTDOWN', {
    time: dueAt.value.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    }),
    minutes: minutesLeft.value,
  });
});

const update = async (customAttributes, success) => {
  try {
    await store.dispatch('updateCustomAttributes', {
      conversationId: currentChat.value.id,
      customAttributes,
      merge: true,
    });
    useAlert(success);
  } catch (error) {
    useAlert(t('CONVERSATION.BOT_ASSIST.ERROR'));
  }
};

const claim = async () => {
  if (currentChat.value?.meta?.assignee?.id !== currentUser.value?.id) {
    await store.dispatch('assignAgent', {
      conversationId: currentChat.value.id,
      agentId: currentUser.value.id,
    });
  }
  await update(
    { claimed_by: String(currentUser.value.id) },
    t('CONVERSATION.BOT_ASSIST.CLAIM_SUCCESS')
  );
};
const replyNow = () =>
  update(
    { bot_fallback_at: new Date().toISOString() },
    t('CONVERSATION.BOT_ASSIST.REPLY_NOW_SUCCESS')
  );
const release = () =>
  update({ claimed_by: '' }, t('CONVERSATION.BOT_ASSIST.RELEASE_SUCCESS'));
</script>

<template>
  <NextBanner
    v-if="isCounting || claimedBy"
    :color="isCounting ? 'amber' : 'slate'"
    class="mx-2 mb-2"
  >
    {{ message }}
    <template #actions>
      <div class="flex gap-2">
        <NextButton
          v-if="!isMine"
          xs
          :label="$t('CONVERSATION.BOT_ASSIST.CLAIM')"
          @click="claim"
        />
        <NextButton
          v-if="isCounting && minutesLeft > 0"
          xs
          faded
          :label="$t('CONVERSATION.BOT_ASSIST.REPLY_NOW')"
          @click="replyNow"
        />
        <NextButton
          v-if="isMine"
          xs
          faded
          :label="$t('CONVERSATION.BOT_ASSIST.RELEASE')"
          @click="release"
        />
      </div>
    </template>
  </NextBanner>
</template>
