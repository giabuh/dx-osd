class Api::V1::Accounts::LocaleOverridesController < Api::V1::Accounts::BaseController
  def index
    authorize Current.account, :show?
    return render_invalid_request unless valid_locale?

    overrides = Current.account.account_locale_overrides.where(locale: params[:locale]).pluck(:key, :value).to_h
    render json: { overrides: overrides }
  end

  def update
    authorize Current.account, :update?
    return render_invalid_request unless valid_key_and_locale?
    return destroy_override if params[:value] == ''
    return render_invalid_request unless params[:value].is_a?(String)

    translation = Current.account.account_locale_overrides.find_or_initialize_by(locale: params[:locale], key: params[:key])
    translation.assign_attributes(value: params[:value], edited_by: current_user)
    render_saved_override(translation)
  end

  def destroy
    authorize Current.account, :update?
    return render_invalid_request unless valid_key_and_locale?

    destroy_override
  end

  private

  def render_saved_override(translation)
    if translation.save
      render json: { locale: translation.locale, key: translation.key, value: translation.value }
    else
      render json: { errors: translation.errors.full_messages }, status: :unprocessable_entity
    end
  end

  def valid_locale?
    DashboardLocaleCatalog.supported_locale?(params[:locale])
  end

  def valid_key_and_locale?
    valid_locale? && DashboardLocaleCatalog.value('en', params[:key]).present?
  end

  def destroy_override
    Current.account.account_locale_overrides.find_by(locale: params[:locale], key: params[:key])&.destroy!
    head :no_content
  end

  def render_invalid_request
    render json: { error: 'Invalid locale override' }, status: :unprocessable_entity
  end
end
