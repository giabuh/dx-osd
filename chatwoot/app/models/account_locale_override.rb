class AccountLocaleOverride < ApplicationRecord
  ALLOWED_TAGS = %w[b strong i em u ins s strike del a code pre blockquote br].freeze
  ALLOWED_ATTRIBUTES = %w[href].freeze
  PLACEHOLDER = /%?\{[a-zA-Z0-9_]+\}/

  belongs_to :account
  belongs_to :edited_by, class_name: 'User'

  validates :locale, presence: true
  validates :key, presence: true, uniqueness: { scope: [:account_id, :locale] }
  validates :value, presence: true, length: { maximum: 4000 }
  validate :validate_catalog_key_and_value

  private

  def validate_catalog_key_and_value
    unless DashboardLocaleCatalog.supported_locale?(locale)
      errors.add(:locale, 'is not supported')
      return
    end

    source = DashboardLocaleCatalog.value('en', key)
    unless source
      errors.add(:key, 'is not in the dashboard catalog')
      return
    end

    return if value.blank?

    errors.add(:value, 'must preserve interpolation placeholders and plural forms') unless placeholders_match?(source)
    errors.add(:value, 'contains unsafe markup') unless safe_markup?
  end

  def placeholders_match?(source)
    source_branches = source.split(/\s*\|\s*/, -1)
    value_branches = value.split(/\s*\|\s*/, -1)
    source_branches.length == value_branches.length &&
      source_branches.zip(value_branches).all? { |original, translated| original.scan(PLACEHOLDER).sort == translated.scan(PLACEHOLDER).sort }
  end

  def safe_markup?
    sanitized = Rails::HTML5::SafeListSanitizer.new.sanitize(value, tags: ALLOWED_TAGS, attributes: ALLOWED_ATTRIBUTES)
    sanitized == value
  end
end
