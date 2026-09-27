FactoryBot.define do
  factory :account_locale_override do
    account
    association :edited_by, factory: :user
    locale { 'vi' }
    key { 'SIDEBAR.CONVERSATIONS' }
    value { 'Cuộc trò chuyện' }
  end
end
