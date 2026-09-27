require 'rails_helper'

RSpec.describe DashboardLocaleCatalog do
  describe '.value' do
    it 'returns a shipped English leaf value' do
      expect(described_class.value('en', 'SIDEBAR.CONVERSATIONS')).to eq('Conversations')
    end

    it 'does not expose unknown or prototype-like keys' do
      expect(described_class.value('en', 'SIDEBAR.UNKNOWN')).to be_nil
      expect(described_class.value('en', '__proto__.polluted')).to be_nil
      expect(described_class.value('en', 'SIDEBAR.constructor')).to be_nil
    end

    it 'does not expose files omitted from the dashboard locale bundle' do
      expect(described_class.value('en', 'WEBHOOKS_SETTINGS.HEADER')).to be_nil
    end
  end

  describe '.supported_locale?' do
    it 'accepts enabled Vietnamese and rejects unknown language codes' do
      expect(described_class.supported_locale?('vi')).to be(true)
      expect(described_class.supported_locale?('xx')).to be(false)
    end
  end
end
