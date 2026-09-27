<script setup>
import { computed, inject, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useAccount } from 'dashboard/composables/useAccount';
import i18nMessages from 'dashboard/i18n';
import LocaleOverridesAPI from 'dashboard/api/localeOverrides';
import { buildTranslationRows, filterTranslationRows } from './catalog';

const { t } = useI18n();
const { accountId } = useAccount();
const accountOverrideLoader = inject('accountOverrideLoader');

const overrides = ref({});
const search = ref('');
const status = ref('all');
const editingKey = ref('');
const draft = ref('');
const errorMessage = ref('');
const isLoading = ref(true);
const savingKey = ref('');

const rows = computed(() => buildTranslationRows({
  english: i18nMessages.en,
  vietnamese: i18nMessages.vi,
  overrides: overrides.value,
}));
const filteredRows = computed(() => filterTranslationRows(rows.value, {
  search: search.value,
  status: status.value,
}));
const visibleRows = computed(() => filteredRows.value.slice(0, 50));
const filters = computed(() => [
  { value: 'all', label: t('LOCALE_OVERRIDES.ALL') },
  { value: 'missing', label: t('LOCALE_OVERRIDES.MISSING') },
  { value: 'unchanged', label: t('LOCALE_OVERRIDES.UNCHANGED') },
  { value: 'overridden', label: t('LOCALE_OVERRIDES.OVERRIDDEN') },
  { value: 'translated', label: t('LOCALE_OVERRIDES.TRANSLATED') },
]);

const load = async () => {
  isLoading.value = true;
  try {
    const response = await LocaleOverridesAPI.list(accountId.value, 'vi');
    overrides.value = response.overrides;
    errorMessage.value = '';
  } catch {
    errorMessage.value = t('LOCALE_OVERRIDES.LOAD_ERROR');
  } finally {
    isLoading.value = false;
  }
};

const edit = row => {
  editingKey.value = row.key;
  draft.value = overrides.value[row.key] ?? row.base;
  errorMessage.value = '';
};

const save = async () => {
  const key = editingKey.value;
  if (!key) return;

  savingKey.value = key;
  errorMessage.value = '';
  try {
    if (draft.value === '') {
      await LocaleOverridesAPI.remove(accountId.value, { locale: 'vi', key });
      const updated = { ...overrides.value };
      delete updated[key];
      overrides.value = updated;
    } else {
      await LocaleOverridesAPI.save(accountId.value, { locale: 'vi', key, value: draft.value });
      overrides.value = { ...overrides.value, [key]: draft.value };
    }
    const refreshed = await accountOverrideLoader.refresh(accountId.value);
    if (!refreshed.ok) {
      errorMessage.value = t('LOCALE_OVERRIDES.REFRESH_ERROR');
      return;
    }
    editingKey.value = '';
  } catch (error) {
    errorMessage.value = error?.response?.data?.errors?.join(', ') ||
      error?.response?.data?.error || t('LOCALE_OVERRIDES.ERROR');
  } finally {
    savingKey.value = '';
  }
};

const reset = async key => {
  savingKey.value = key;
  errorMessage.value = '';
  try {
    await LocaleOverridesAPI.remove(accountId.value, { locale: 'vi', key });
    const updated = { ...overrides.value };
    delete updated[key];
    overrides.value = updated;
    const refreshed = await accountOverrideLoader.refresh(accountId.value);
    if (!refreshed.ok) {
      errorMessage.value = t('LOCALE_OVERRIDES.REFRESH_ERROR');
      return;
    }
    editingKey.value = '';
  } catch (error) {
    errorMessage.value = error?.response?.data?.errors?.join(', ') ||
      error?.response?.data?.error || t('LOCALE_OVERRIDES.ERROR');
  } finally {
    savingKey.value = '';
  }
};

onMounted(load);
</script>

<template>
  <div class="w-full space-y-5">
    <header class="space-y-1">
      <h1 class="text-xl font-semibold text-n-slate-12">
        {{ t('LOCALE_OVERRIDES.TITLE') }}
      </h1>
      <p class="text-sm text-n-slate-11">
        {{ t('LOCALE_OVERRIDES.DESCRIPTION') }}
      </p>
    </header>

    <div class="flex flex-wrap gap-3">
      <input
        v-model="search"
        type="search"
        :aria-label="t('LOCALE_OVERRIDES.SEARCH')"
        :placeholder="t('LOCALE_OVERRIDES.SEARCH')"
        class="min-w-64 flex-1 rounded-lg border border-n-weak bg-n-background px-3 py-2 text-sm text-n-slate-12"
      />
      <select
        v-model="status"
        :aria-label="t('LOCALE_OVERRIDES.FILTER')"
        class="rounded-lg border border-n-weak bg-n-background px-3 py-2 text-sm text-n-slate-12"
      >
        <option v-for="option in filters" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </div>

    <p v-if="errorMessage" role="alert" class="text-sm text-n-ruby-11">
      {{ errorMessage }}
    </p>
    <p v-if="isLoading" class="text-sm text-n-slate-11">
      {{ t('LOCALE_OVERRIDES.LOADING') }}
    </p>
    <template v-else>
      <p class="text-xs text-n-slate-11">
        {{ t('LOCALE_OVERRIDES.COUNT', { count: filteredRows.length }) }}
      </p>
      <p v-if="!filteredRows.length" class="text-sm text-n-slate-11">
        {{ t('LOCALE_OVERRIDES.NO_RESULTS') }}
      </p>

      <div v-for="row in visibleRows" :key="row.key" class="rounded-lg border border-n-weak bg-n-background p-4 space-y-3">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 space-y-1">
            <code class="break-all text-xs text-n-slate-11">{{ row.key }}</code>
            <p class="text-sm font-medium text-n-slate-12">{{ row.source }}</p>
          </div>
          <span class="rounded-md bg-n-slate-3 px-2 py-1 text-xs text-n-slate-11">
            {{ t(`LOCALE_OVERRIDES.${row.status.toUpperCase()}`) }}
          </span>
        </div>
        <div class="grid gap-2 text-sm text-n-slate-11 sm:grid-cols-2">
          <p>{{ t('LOCALE_OVERRIDES.BASE') }}: {{ row.base || '—' }}</p>
          <p>{{ t('LOCALE_OVERRIDES.EFFECTIVE') }}: <span class="text-n-slate-12">{{ row.effective }}</span></p>
        </div>
        <div class="flex gap-2">
          <button
            type="button"
            :aria-label="t('LOCALE_OVERRIDES.EDIT_KEY', { key: row.key })"
            class="rounded-lg border border-n-weak px-3 py-1.5 text-sm text-n-slate-12"
            @click="edit(row)"
          >
            {{ t('LOCALE_OVERRIDES.EDIT') }}
          </button>
          <button
            v-if="row.status === 'overridden'"
            type="button"
            :aria-label="t('LOCALE_OVERRIDES.RESET_KEY', { key: row.key })"
            :disabled="savingKey === row.key"
            class="rounded-lg border border-n-weak px-3 py-1.5 text-sm text-n-slate-12"
            @click="reset(row.key)"
          >
            {{ t('LOCALE_OVERRIDES.RESET') }}
          </button>
        </div>
        <div v-if="editingKey === row.key" class="space-y-2">
          <label class="block text-sm text-n-slate-11">{{ t('LOCALE_OVERRIDES.VALUE') }}</label>
          <textarea
            v-model="draft"
            :aria-label="t('LOCALE_OVERRIDES.VALUE')"
            rows="3"
            class="w-full rounded-lg border border-n-weak bg-n-background px-3 py-2 text-sm text-n-slate-12"
          />
          <div class="flex gap-2">
            <button
              type="button"
              :aria-label="t('LOCALE_OVERRIDES.SAVE')"
              :disabled="savingKey === row.key"
              class="rounded-lg bg-n-brand px-3 py-1.5 text-sm text-white"
              @click="save"
            >
              {{ t('LOCALE_OVERRIDES.SAVE') }}
            </button>
            <button
              type="button"
              class="rounded-lg border border-n-weak px-3 py-1.5 text-sm text-n-slate-12"
              @click="editingKey = ''"
            >
              {{ t('LOCALE_OVERRIDES.CANCEL') }}
            </button>
          </div>
        </div>
      </div>
      <p v-if="filteredRows.length > visibleRows.length" class="text-xs text-n-slate-11">
        {{ t('LOCALE_OVERRIDES.SEARCH_MORE') }}
      </p>
    </template>
  </div>
</template>
