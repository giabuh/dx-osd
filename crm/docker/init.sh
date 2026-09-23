#!bin/bash

if [ -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo "Bench already exists, skipping init"
    cd frappe-bench
    bench start
else
    echo "Creating new bench..."
fi

# Frappe is pinned (not vendored) to the version the vendored crm/ is tested on. See docs/vendored-upstreams.md.
bench init --skip-redis-config-generation frappe-bench --frappe-branch v15.121.1

cd frappe-bench

# Use containers instead of localhost
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

# Run the vendored crm/ source (bind-mounted at /home/frappe/crm) instead of cloning it from GitHub.
# Its frontend depends on link:../../frappe/ui, so frappe must sit beside it in /home/frappe.
ln -sfn /home/frappe/frappe-bench/apps/frappe /home/frappe/frappe
ln -s /home/frappe/crm apps/crm
./env/bin/pip install -e apps/crm
(cd apps/crm && yarn install)
sed -i -e '$a\' sites/apps.txt && echo crm >> sites/apps.txt
bench build --app crm

# mmm_custom is bind-mounted outside the bench (mounting it under apps/ makes
# Docker pre-create frappe-bench/, which breaks `bench init`); link it in.
ln -s /home/frappe/mmm_custom apps/mmm_custom
./env/bin/pip install -e apps/mmm_custom
sed -i -e '$a\' sites/apps.txt && echo mmm_custom >> sites/apps.txt

bench new-site crm.localhost \
    --force \
    --mariadb-root-password 123 \
    --admin-password admin \
    --no-mariadb-socket

bench --site crm.localhost install-app crm
bench --site crm.localhost install-app mmm_custom
bench --site crm.localhost set-config developer_mode 1
bench --site crm.localhost set-config mute_emails 1
bench --site crm.localhost set-config server_script_enabled 1
bench --site crm.localhost clear-cache
bench use crm.localhost

bench start