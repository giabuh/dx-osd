import { createI18n } from 'vue-i18n';
import { describe, expect, it, vi } from 'vitest';
import { createAccountOverrideLoader } from '../accountOverrides';

const baseMessages = {
  SIDEBAR: { CONVERSATIONS: 'Cuộc trò chuyện' },
};

const makeComposer = () =>
  createI18n({
    legacy: false,
    locale: 'vi',
    messages: {
      en: { SIDEBAR: { CONVERSATIONS: 'Conversations', CONTACTS: 'Contacts' } },
      vi: structuredClone(baseMessages),
    },
  }).global;

describe('account override loader', () => {
  it('shows the active account override in Vietnamese and leaves English unchanged', async () => {
    const composer = makeComposer();
    const fetchOverrides = vi.fn(async () => ({
      overrides: { 'SIDEBAR.CONVERSATIONS': 'Hội thoại' },
    }));
    const loader = createAccountOverrideLoader({
      composer,
      fetchOverrides,
      baseMessages,
    });

    expect(await loader.load(1)).toEqual({ ok: true });
    expect(composer.t('SIDEBAR.CONVERSATIONS')).toBe('Hội thoại');
    composer.locale.value = 'en';
    expect(composer.t('SIDEBAR.CONVERSATIONS')).toBe('Conversations');
  });

  it('removes the previous account text when the next account has no override', async () => {
    const composer = makeComposer();
    const fetchOverrides = vi.fn(async accountId => ({
      overrides:
        accountId === 1 ? { 'SIDEBAR.CONVERSATIONS': 'Hội thoại A' } : {},
    }));
    const loader = createAccountOverrideLoader({
      composer,
      fetchOverrides,
      baseMessages,
    });

    await loader.load(1);
    await loader.load(2);

    expect(composer.t('SIDEBAR.CONVERSATIONS')).toBe('Cuộc trò chuyện');
  });

  it('discards a late response from the previous account', async () => {
    const composer = makeComposer();
    let resolveFirst;
    const first = new Promise(resolve => {
      resolveFirst = resolve;
    });
    const fetchOverrides = vi.fn(accountId =>
      accountId === 1
        ? first
        : Promise.resolve({
            overrides: { 'SIDEBAR.CONVERSATIONS': 'Hội thoại B' },
          })
    );
    const loader = createAccountOverrideLoader({
      composer,
      fetchOverrides,
      baseMessages,
    });

    const loadingFirst = loader.load(1);
    await loader.load(2);
    resolveFirst({ overrides: { 'SIDEBAR.CONVERSATIONS': 'Hội thoại A' } });
    await loadingFirst;

    expect(composer.t('SIDEBAR.CONVERSATIONS')).toBe('Hội thoại B');
  });

  it('applies a key missing from base Vietnamese while ignoring unknown and prototype-like keys', async () => {
    const composer = makeComposer();
    const fetchOverrides = vi.fn(async () => ({
      overrides: {
        'SIDEBAR.CONTACTS': 'Liên hệ',
        'SIDEBAR.UNKNOWN': 'Unexpected',
        '__proto__.polluted': 'Unsafe',
      },
    }));
    const loader = createAccountOverrideLoader({
      composer,
      fetchOverrides,
      baseMessages,
    });

    await loader.load(1);

    expect(composer.t('SIDEBAR.CONTACTS')).toBe('Liên hệ');
    expect(composer.getLocaleMessage('vi').SIDEBAR.UNKNOWN).toBeUndefined();
    expect({}.polluted).toBeUndefined();
  });

  it('restores shipped Vietnamese and reports a fetch failure', async () => {
    const composer = makeComposer();
    const fetchOverrides = vi
      .fn()
      .mockResolvedValueOnce({
        overrides: { 'SIDEBAR.CONVERSATIONS': 'Hội thoại A' },
      })
      .mockRejectedValueOnce(new Error('network'));
    const loader = createAccountOverrideLoader({
      composer,
      fetchOverrides,
      baseMessages,
    });

    await loader.load(1);
    const result = await loader.load(2);

    expect(result).toMatchObject({ ok: false, error: expect.any(Error) });
    expect(composer.t('SIDEBAR.CONVERSATIONS')).toBe('Cuộc trò chuyện');
  });
});
