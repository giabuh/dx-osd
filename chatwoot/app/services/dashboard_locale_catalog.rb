class DashboardLocaleCatalog
  FORBIDDEN_SEGMENTS = %w[__proto__ prototype constructor].freeze

  def self.supported_locale?(locale)
    LANGUAGES_CONFIG.values.any? { |language| language[:iso_639_1_code] == locale }
  end

  def self.value(locale, key)
    return unless supported_locale?(locale)
    return unless valid_key?(key)

    catalog(locale)[key]
  end

  def self.valid_key?(key)
    key.is_a?(String) && key.split('.').all? { |segment| segment.present? && FORBIDDEN_SEGMENTS.exclude?(segment) }
  end

  def self.catalog(locale)
    @catalogs ||= {}
    @catalogs[locale] ||= begin
      directory = Rails.root.join('app/javascript/dashboard/i18n/locale', locale)
      imports = File.read(directory.join('index.js')).scan(%r{^import \w+ from '\./(\w+\.json)';$}).flatten
      imports.each_with_object({}) do |file, entries|
        flatten(JSON.parse(File.read(directory.join(file))), nil, entries)
      end.freeze
    end
  end

  def self.flatten(node, prefix, entries)
    node.each do |name, value|
      key = [prefix, name].compact.join('.')
      if value.is_a?(Hash)
        flatten(value, key, entries)
      elsif value.is_a?(String)
        raise "Duplicate dashboard locale key: #{key}" if entries.key?(key)

        entries[key] = value
      end
    end
  end
  private_class_method :catalog, :flatten
end
