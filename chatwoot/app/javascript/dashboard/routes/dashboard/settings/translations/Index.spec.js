import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { withFullI18n } from 'test-i18n';
import Index from './Index.vue';
import routes from './translations.routes';

withFullI18n();

const api = vi.hoisted(() => ({
  list: vi.fn(),
  save: vi.fn(),
  remove: vi.fn(),
}));

vi.mock('dashboard/api/localeOverrides', () => ({ default: api }));
vi.mock('dashboard/composables/useAccount', () => ({
  useAccount: () => ({ accountId: { value: 1 } }),
}));

const mountEditor = async () => {
  const loader = { refresh: vi.fn().mockResolvedValue({ ok: true }) };
  const wrapper = mount(Index, {
    global: { provide: { accountOverrideLoader: loader } },
  });
  await flushPromises();
  return { wrapper, loader };
};

describe('Vietnamese translation editor', () => {
  beforeEach(() => {
    api.list.mockReset().mockResolvedValue({ overrides: {} });
    api.save.mockReset().mockResolvedValue({
      locale: 'vi',
      key: 'SIDEBAR.CONVERSATIONS',
      value: 'Hội thoại mới',
    });
    api.remove.mockReset().mockResolvedValue(undefined);
  });

  it('restricts its route to account administrators', () => {
    expect(routes.routes[0].children[0].meta.permissions).toEqual([
      'administrator',
    ]);
    expect(routes.routes[0].props).toEqual({ keepAlive: false });
  });

  it('searches a key and saves Vietnamese copy in the visible row', async () => {
    const { wrapper, loader } = await mountEditor();
    await wrapper
      .get('input[aria-label="Search translations"]')
      .setValue('SIDEBAR.CONVERSATIONS');
    await wrapper
      .get('button[aria-label="Edit SIDEBAR.CONVERSATIONS"]')
      .trigger('click');
    await wrapper
      .get('textarea[aria-label="Vietnamese text"]')
      .setValue('Hội thoại mới');
    await wrapper.get('button[aria-label="Save"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Hội thoại mới');
    expect(loader.refresh).toHaveBeenCalledWith(1);
  });

  it('resets an override to built-in Vietnamese', async () => {
    api.list.mockResolvedValue({
      overrides: { 'SIDEBAR.CONVERSATIONS': 'Hội thoại riêng' },
    });
    const { wrapper } = await mountEditor();
    await wrapper
      .get('input[aria-label="Search translations"]')
      .setValue('SIDEBAR.CONVERSATIONS');

    expect(wrapper.text()).toContain('Hội thoại riêng');
    await wrapper
      .get('button[aria-label="Reset SIDEBAR.CONVERSATIONS"]')
      .trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Cuộc trò chuyện');
    expect(wrapper.text()).not.toContain('Hội thoại riêng');
  });

  it('shows validation errors and keeps the previous effective value', async () => {
    api.list.mockResolvedValue({
      overrides: { 'SIDEBAR.CONVERSATIONS': 'Hội thoại riêng' },
    });
    api.save.mockRejectedValue({
      response: { data: { errors: ['Invalid value'] } },
    });
    const { wrapper } = await mountEditor();
    await wrapper
      .get('input[aria-label="Search translations"]')
      .setValue('SIDEBAR.CONVERSATIONS');
    await wrapper
      .get('button[aria-label="Edit SIDEBAR.CONVERSATIONS"]')
      .trigger('click');
    await wrapper
      .get('textarea[aria-label="Vietnamese text"]')
      .setValue('<script>unsafe</script>');
    await wrapper.get('button[aria-label="Save"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Invalid value');
    expect(wrapper.text()).toContain('Hội thoại riêng');
  });

  it('reports a failed dashboard refresh after the server saves a translation', async () => {
    const { wrapper, loader } = await mountEditor();
    loader.refresh.mockResolvedValue({
      ok: false,
      error: new Error('offline'),
    });
    await wrapper
      .get('input[aria-label="Search translations"]')
      .setValue('SIDEBAR.CONVERSATIONS');
    await wrapper
      .get('button[aria-label="Edit SIDEBAR.CONVERSATIONS"]')
      .trigger('click');
    await wrapper
      .get('textarea[aria-label="Vietnamese text"]')
      .setValue('Hội thoại mới');
    await wrapper.get('button[aria-label="Save"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('saved, but');
    expect(
      wrapper.find('textarea[aria-label="Vietnamese text"]').exists()
    ).toBe(true);
  });
});
