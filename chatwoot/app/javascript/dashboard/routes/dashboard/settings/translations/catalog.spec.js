import { describe, expect, it } from 'vitest';
import { buildTranslationRows, filterTranslationRows } from './catalog';

const english = {
  SIDEBAR: {
    CONVERSATIONS: 'Conversations',
    CONTACTS: 'Contacts',
    REPORTS: 'Reports',
    SETTINGS: 'Settings',
  },
};
const vietnamese = {
  SIDEBAR: {
    CONVERSATIONS: 'Cuộc trò chuyện',
    REPORTS: 'Reports',
    SETTINGS: 'Cài đặt',
  },
};
const overrides = { 'SIDEBAR.CONTACTS': 'Liên hệ' };

describe('translation catalog', () => {
  it('shows shipped, missing, unchanged, and overridden values by dotted key', () => {
    const rows = buildTranslationRows({ english, vietnamese, overrides });

    expect(rows.find(row => row.key === 'SIDEBAR.CONVERSATIONS')).toEqual({
      key: 'SIDEBAR.CONVERSATIONS',
      source: 'Conversations',
      base: 'Cuộc trò chuyện',
      effective: 'Cuộc trò chuyện',
      status: 'translated',
    });
    expect(rows.find(row => row.key === 'SIDEBAR.CONTACTS')).toEqual({
      key: 'SIDEBAR.CONTACTS',
      source: 'Contacts',
      base: '',
      effective: 'Liên hệ',
      status: 'overridden',
    });
    expect(rows.find(row => row.key === 'SIDEBAR.REPORTS').status).toBe(
      'unchanged'
    );
    expect(
      buildTranslationRows({ english, vietnamese, overrides: {} }).find(
        row => row.key === 'SIDEBAR.CONTACTS'
      ).status
    ).toBe('missing');
  });

  it('searches English text and keys and filters by status', () => {
    const rows = buildTranslationRows({ english, vietnamese, overrides });

    expect(
      filterTranslationRows(rows, {
        search: 'conversations',
        status: 'all',
      }).map(row => row.key)
    ).toEqual(['SIDEBAR.CONVERSATIONS']);
    expect(
      filterTranslationRows(rows, {
        search: 'SIDEBAR.CONTACTS',
        status: 'all',
      }).map(row => row.key)
    ).toEqual(['SIDEBAR.CONTACTS']);
    expect(
      filterTranslationRows(rows, { search: '', status: 'unchanged' }).map(
        row => row.key
      )
    ).toEqual(['SIDEBAR.REPORTS']);
    expect(
      filterTranslationRows(rows, { search: '', status: 'overridden' }).map(
        row => row.key
      )
    ).toEqual(['SIDEBAR.CONTACTS']);
  });
});
