# frozen_string_literal: true

# Allow Chatwoot to be embedded seamlessly within the Frappe CRM dashboard
Rails.application.config.action_dispatch.default_headers.delete('X-Frame-Options')
