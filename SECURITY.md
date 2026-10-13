# Security Policy

We take the security of **DX-OSD (Open-Core DX-Lab)** very seriously. As an open-source platform managing customer and organizational data, ensuring robust security boundaries and data protection is our highest priority.

---

## Supported Versions

| Version | Supported | Notes |
|---|---|---|
| `1.0.x-dev` | ✅ Yes | Active development branch for OLP PMNM 2026 |
| `< 1.0.0` | ❌ No | Historical prototype branches |

---

## Security Architecture & Best Practices

1. **Local Port Binding**: All service ports (`3000`, `8000`, `9000`, `15432`, `16379`) bind strictly to `127.0.0.1`. In production deployments, Caddy serves as the sole reverse proxy providing TLS termination and rate limiting.
2. **HMAC-SHA256 Webhook Verification**: All incoming webhooks from external channels or Chatwoot enforce cryptographic HMAC-SHA256 signature verification combined with a 300-second anti-replay timestamp window. No default fallback secret is permitted in production.
3. **Role-Based Access Control (RBAC)**: Custom permissions isolate branch-level data via `scope.py` and prevent unauthorized access to sensitive customer or lead records.
4. **Secret Management**: Sensitive keys, webhook secrets, and API credentials are kept exclusively in `.env` or `site_config.json` and must never be committed to version control.

---

## Reporting a Vulnerability

**Please DO NOT report security vulnerabilities through public GitHub Issues.**

If you discover a security vulnerability or weakness:
1. Send an email with full details to: **thanhheo7749@gmail.com** (or maintainers via GitHub Security Advisories).
2. Please include:
   - Vulnerability category and impact assessment.
   - Affected component (`chatwoot/`, `crm/`, `mmm_custom/`, or Docker configuration).
   - Clear reproduction steps or Proof of Concept (PoC).

We will acknowledge reports within 48 hours and work on a coordinated fix and security patch.
