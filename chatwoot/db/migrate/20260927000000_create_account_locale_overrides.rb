class CreateAccountLocaleOverrides < ActiveRecord::Migration[7.1]
  def change
    create_table :account_locale_overrides do |t|
      t.references :account, null: false, foreign_key: true
      t.references :edited_by, null: false, foreign_key: { to_table: :users }
      t.string :locale, null: false
      t.string :key, null: false
      t.text :value, null: false
      t.timestamps
    end

    add_index :account_locale_overrides, [:account_id, :locale, :key], unique: true,
                                                                       name: 'index_account_locale_overrides_on_account_locale_key'
  end
end
