require 'rails_helper'

RSpec.describe AccountLocaleOverride do
  let(:account) { create(:account) }
  let(:admin) { create(:user, account: account, role: :administrator) }

  it 'stores one valid Vietnamese translation for an account' do
    translation = described_class.create!(account: account, edited_by: admin, locale: 'vi',
                                          key: 'SIDEBAR.CONVERSATIONS', value: 'Cuộc trò chuyện')

    expect(translation.reload.value).to eq('Cuộc trò chuyện')
    expect(account.account_locale_overrides).to include(translation)
  end

  it 'rejects a duplicate account, locale, and key' do
    attributes = { account: account, edited_by: admin, locale: 'vi', key: 'SIDEBAR.CONVERSATIONS', value: 'Cuộc trò chuyện' }
    described_class.create!(attributes)

    expect(described_class.new(attributes)).not_to be_valid
  end

  it 'rejects unknown and prototype-like keys' do
    %w[SIDEBAR.UNKNOWN SIDEBAR.__proto__.polluted].each do |key|
      translation = described_class.new(account: account, edited_by: admin, locale: 'vi', key: key, value: 'Văn bản')
      expect(translation).not_to be_valid
    end
  end

  it 'rejects a value longer than 4000 characters' do
    translation = described_class.new(account: account, edited_by: admin, locale: 'vi',
                                      key: 'SIDEBAR.CONVERSATIONS', value: 'a' * 4001)

    expect(translation).not_to be_valid
  end

  it 'preserves the existing value when an update drops interpolation placeholders' do
    translation = described_class.create!(account: account, edited_by: admin, locale: 'vi',
                                          key: 'APP_GLOBAL.IMPERSONATION.MESSAGE',
                                          value: 'Bạn đang đại diện cho {name} ({email}).')

    expect(translation.update(value: 'Bạn đang đại diện cho {name}.')).to be(false)
    expect(translation.reload.value).to eq('Bạn đang đại diện cho {name} ({email}).')
  end

  it 'rejects a plural translation that loses a placeholder in one branch' do
    translation = described_class.new(account: account, edited_by: admin, locale: 'vi',
                                      key: 'BULK_ACTION.ASSIGN_AGENT_CONFIRMATION_LABEL',
                                      value: 'Gán {n} cuộc trò chuyện cho {agentName}? | Gán {n} cuộc trò chuyện?')

    expect(translation).not_to be_valid
  end

  it 'rejects script tags and event-handler markup' do
    ['<script>alert(1)</script>', '<img src=x onerror=alert(1)>'].each do |value|
      translation = described_class.new(account: account, edited_by: admin, locale: 'vi',
                                        key: 'SIDEBAR.CONVERSATIONS', value: value)
      expect(translation).not_to be_valid
    end
  end
end
