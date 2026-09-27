# Cloudflare Tunnel (public entry for Meta webhooks)

Meta (Messenger/Instagram) must reach Chatwoot over public HTTPS. A named Cloudflare Tunnel does this without opening any port: every service keeps binding `127.0.0.1` only, and `cloudflared` dials out to Cloudflare.

| Item | Value |
|---|---|
| Tunnel name / id | `dx-osd` / `984bd08f-d9d8-4ec6-b20c-e4313a6df55c` |
| Zone | `lflow.site` (the zone authorized at `cloudflared tunnel login`) |
| Public hostname | `chat.lflow.site` → `http://127.0.0.1:3000` (Chatwoot) |
| Not exposed | CRM (`127.0.0.1:8000`). Chatwoot → CRM webhooks stay on localhost |
| Runs as | systemd service `cloudflared` |

This replaces the throwaway `cloudflared tunnel --url http://127.0.0.1:3000` (random `trycloudflare.com` URL) mentioned in the FOSS integration plan.

## Secrets

Never commit or print the tunnel credentials (`~/.cloudflared/<id>.json`, `/etc/cloudflared/<id>.json`) or `~/.cloudflared/cert.pem`. Only `config.yml` below is safe to share. To revoke, delete the tunnel: `cloudflared tunnel delete dx-osd`.

## Setup from scratch

Prerequisite: the domain is a zone in the Cloudflare account.

```bash
cloudflared tunnel login                    # pick the zone in the browser; writes ~/.cloudflared/cert.pem
cloudflared tunnel create dx-osd            # writes ~/.cloudflared/<id>.json
cloudflared tunnel route dns dx-osd chat.lflow.site
```

`route dns` appends the zone of the login certificate to any hostname that is not inside it. Passing `chat.flow.site` while logged in to `lflow.site` silently creates `chat.flow.site.lflow.site`. Check the `Added CNAME ...` line in the output.

Config (`/etc/cloudflared/config.yml`):

```yaml
tunnel: 984bd08f-d9d8-4ec6-b20c-e4313a6df55c
credentials-file: /etc/cloudflared/984bd08f-d9d8-4ec6-b20c-e4313a6df55c.json

ingress:
  - hostname: chat.lflow.site
    service: http://127.0.0.1:3000
  - service: http_status:404
```

Install as a service. `sudo` does not see `~/.local/bin`, so use the full path:

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/config.yml ~/.cloudflared/<id>.json /etc/cloudflared/
sudo sed -i 's#/home/giabao/.cloudflared#/etc/cloudflared#' /etc/cloudflared/config.yml
sudo "$(command -v cloudflared)" service install
```

The unit's `ExecStart` points at the binary's current path. If the binary moves or is replaced elsewhere, reinstall the service.

## Verify

```bash
systemctl is-active cloudflared                                  # active
cloudflared tunnel list                                          # dx-osd shows 4 connections
curl -s -o /dev/null -w "%{http_code}\n" https://chat.lflow.site # 200/302
```

## Chatwoot and Meta settings

- `chatwoot/.env`: `FRONTEND_URL=https://chat.lflow.site`, then restart `chatwoot-rails` and `chatwoot-sidekiq`. Without it Chatwoot builds `localhost` links.
- Meta App → Webhooks callback URL: `https://chat.lflow.site/bot`, verify token equal to `FB_VERIFY_TOKEN`.
- Meta App → Facebook Login OAuth redirect URIs: use the `chat.lflow.site` origin.

## Adding another hostname

Add an `ingress` entry above the `http_status:404` catch-all, run `cloudflared tunnel route dns dx-osd <host>`, then `sudo systemctl restart cloudflared`. For CRM, set `originRequest.httpHostHeader: crm.localhost` (same as `docker/caddy/Caddyfile`); expose it only if there is a real need.
