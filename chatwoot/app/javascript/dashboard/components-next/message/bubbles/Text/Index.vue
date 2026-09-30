<script setup>
import { computed, ref } from 'vue';
import BaseBubble from 'next/message/bubbles/Base.vue';
import FormattedContent from './FormattedContent.vue';
import AttachmentChips from 'next/message/chips/AttachmentChips.vue';
import TranslationToggle from 'dashboard/components-next/message/TranslationToggle.vue';
import { MESSAGE_TYPES } from '../../constants';
import { MESSAGE_STATUS } from 'shared/constants/messages';
import { useMessageContext } from '../../provider.js';
import { useTranslations } from 'dashboard/composables/useTranslations';
import { useStore } from 'vuex';
import { useI18n } from 'vue-i18n';
import { useMapGetter } from 'dashboard/composables/store';
import NextButton from 'dashboard/components-next/button/Button.vue';
import { jevDraftReply } from '../../helpers/jevDraft';

const {
  content,
  attachments,
  contentAttributes,
  messageType,
  status,
  isPrivate,
  conversationId,
} = useMessageContext();

const { hasTranslations, translationContent } =
  useTranslations(contentAttributes);

const renderOriginal = ref(false);

const renderContent = computed(() => {
  if (renderOriginal.value) {
    return content.value;
  }

  if (hasTranslations.value) {
    return translationContent.value;
  }

  return content.value;
});

const isTemplate = computed(() => {
  return messageType.value === MESSAGE_TYPES.TEMPLATE;
});

const contactInfoRequestState = computed(() => {
  if (status.value === MESSAGE_STATUS.FAILED) return null;

  return contentAttributes.value?.whatsappContactInfo?.state;
});

const isEmpty = computed(() => {
  return !content.value && !attachments.value?.length;
});

const handleSeeOriginal = () => {
  renderOriginal.value = !renderOriginal.value;
};

// DX-OSD staff assist: send the reply of a Jev draft note to the customer in one click.
const store = useStore();
const { t } = useI18n();
const currentUser = useMapGetter('getCurrentUser');
const draftReply = computed(() =>
  isPrivate.value ? jevDraftReply(content.value) : null
);
const draftSent = ref(false);
// A failed send shows on the sent message itself, with its retry.
const sendDraft = () => {
  draftSent.value = true;
  store.dispatch('createPendingMessageAndSend', {
    conversationId: conversationId.value,
    message: draftReply.value,
    private: false,
    sender: {
      name: currentUser.value?.name,
      thumbnail: currentUser.value?.avatar_url,
    },
  });
};
</script>

<template>
  <BaseBubble class="px-4 py-3" data-bubble-name="text">
    <div class="gap-3 flex flex-col">
      <span v-if="isEmpty" class="text-n-slate-11">
        {{ $t('CONVERSATION.NO_CONTENT') }}
      </span>
      <FormattedContent v-if="renderContent" :content="renderContent" />
      <span
        v-if="contactInfoRequestState === 'pending'"
        class="text-xs font-medium text-n-slate-11"
      >
        {{ $t('CONVERSATION.REQUEST_CONTACT_INFO.STATES.PENDING') }}
      </span>
      <span
        v-else-if="contactInfoRequestState === 'shared'"
        class="text-xs font-medium text-n-slate-11"
      >
        {{ $t('CONVERSATION.REQUEST_CONTACT_INFO.STATES.SHARED') }}
      </span>
      <span
        v-else-if="contactInfoRequestState === 'identity_conflict'"
        class="text-xs font-medium text-n-slate-11"
      >
        {{ $t('CONVERSATION.REQUEST_CONTACT_INFO.STATES.IDENTITY_CONFLICT') }}
      </span>
      <TranslationToggle
        v-if="hasTranslations"
        class="-mt-3"
        :showing-original="renderOriginal"
        @toggle="handleSeeOriginal"
      />
      <AttachmentChips :attachments="attachments" class="gap-2" />
      <div v-if="draftReply" class="flex justify-end">
        <NextButton
          xs
          icon="i-lucide-send"
          :label="
            draftSent
              ? t('CONVERSATION.BOT_ASSIST.DRAFT_SENT')
              : t('CONVERSATION.BOT_ASSIST.SEND_DRAFT')
          "
          :disabled="draftSent"
          @click="sendDraft"
        />
      </div>
      <template v-if="isTemplate">
        <div
          v-if="contentAttributes.submittedEmail"
          class="px-2 py-1 rounded-lg bg-n-alpha-3"
        >
          {{ contentAttributes.submittedEmail }}
        </div>
      </template>
    </div>
  </BaseBubble>
</template>

<style>
p:last-child {
  margin-bottom: 0;
}
</style>
