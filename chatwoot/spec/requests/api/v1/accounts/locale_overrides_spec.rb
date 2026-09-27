require 'rails_helper'

RSpec.describe 'Account locale overrides API', type: :request do
  let(:account) { create(:account) }
  let(:admin) { create(:user, account: account, role: :administrator) }
  let(:agent) { create(:user, account: account, role: :agent) }
  let(:path) { "/api/v1/accounts/#{account.id}/locale_overrides" }
  let(:key) { 'SIDEBAR.CONVERSATIONS' }

  it 'rejects unauthenticated reads' do
    get path, params: { locale: 'vi' }

    expect(response).to have_http_status(:unauthorized)
  end

  it 'lets an account agent read that account’s overrides' do
    create(:account_locale_override, account: account, edited_by: admin, key: key, value: 'Cuộc trò chuyện')

    get path, params: { locale: 'vi' }, headers: agent.create_new_auth_token

    expect(response).to have_http_status(:ok)
    expect(response.parsed_body).to eq('overrides' => { key => 'Cuộc trò chuyện' })
  end

  it 'lets an administrator save and replace an override' do
    put path, params: { locale: 'vi', key: key, value: 'Các cuộc trò chuyện' }, headers: admin.create_new_auth_token, as: :json

    expect(response).to have_http_status(:ok)
    expect(response.parsed_body).to include('locale' => 'vi', 'key' => key, 'value' => 'Các cuộc trò chuyện')
    expect(account.account_locale_overrides.find_by!(key: key).edited_by).to eq(admin)
  end

  it 'lets an administrator delete an override and treats an absent valid key as deleted' do
    create(:account_locale_override, account: account, edited_by: admin, key: key)

    delete path, params: { locale: 'vi', key: key }, headers: admin.create_new_auth_token, as: :json

    expect(response).to have_http_status(:no_content)
    expect(account.account_locale_overrides.where(key: key)).to be_empty

    delete path, params: { locale: 'vi', key: key }, headers: admin.create_new_auth_token, as: :json
    expect(response).to have_http_status(:no_content)
  end

  it 'treats an empty saved value as reset' do
    create(:account_locale_override, account: account, edited_by: admin, key: key)

    put path, params: { locale: 'vi', key: key, value: '' }, headers: admin.create_new_auth_token, as: :json

    expect(response).to have_http_status(:no_content)
    expect(account.account_locale_overrides.where(key: key)).to be_empty
  end

  it 'forbids an agent from saving or deleting overrides' do
    put path, params: { locale: 'vi', key: key, value: 'Bản dịch' }, headers: agent.create_new_auth_token, as: :json
    expect(response).to have_http_status(:unauthorized)

    delete path, params: { locale: 'vi', key: key }, headers: agent.create_new_auth_token, as: :json
    expect(response).to have_http_status(:unauthorized)
    expect(account.account_locale_overrides).to be_empty
  end

  it 'does not let another account member read or write this account' do
    other_account = create(:account)
    outsider = create(:user, account: other_account, role: :administrator)

    get path, params: { locale: 'vi' }, headers: outsider.create_new_auth_token
    expect(response).to have_http_status(:unauthorized)

    put path, params: { locale: 'vi', key: key, value: 'Bản dịch' }, headers: outsider.create_new_auth_token, as: :json
    expect(response).to have_http_status(:unauthorized)
    expect(account.account_locale_overrides).to be_empty
  end

  it 'rejects an invalid key without changing the previous value' do
    create(:account_locale_override, account: account, edited_by: admin, key: key, value: 'Cuộc trò chuyện')

    put path, params: { locale: 'vi', key: '__proto__.polluted', value: 'Bản dịch' }, headers: admin.create_new_auth_token, as: :json

    expect(response).to have_http_status(:unprocessable_entity)
    expect(account.account_locale_overrides.find_by!(key: key).value).to eq('Cuộc trò chuyện')
  end

  it 'rejects unsafe markup without changing the previous value' do
    create(:account_locale_override, account: account, edited_by: admin, key: key, value: 'Cuộc trò chuyện')

    put path, params: { locale: 'vi', key: key, value: '<img src=x onerror=alert(1)>' },
              headers: admin.create_new_auth_token, as: :json

    expect(response).to have_http_status(:unprocessable_entity)
    expect(account.account_locale_overrides.find_by!(key: key).value).to eq('Cuộc trò chuyện')
  end
end
