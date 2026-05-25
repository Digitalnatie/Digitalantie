# Security Policy

## Supported Versions

| Version          | Supported          |
|------------------|--------------------|
| 18.0.3.x         | ✅ Yes              |
| 18.0.2.x         | ❌ No (internal)    |
| < 18.0           | ❌ No               |

Only the latest published 18.0 release receives security updates.

## Reporting a Vulnerability

If you discover a security vulnerability in **WooCommerce Connector**,
please **do not** open a public issue.

Send a private report to:

**support@digitalnatie.be**

Include:
- A description of the vulnerability
- Steps to reproduce
- Affected version(s)
- The impact you observed
- Your name/handle for credit (optional)

You will receive an acknowledgement within **3 working days** and a fix
plan within **10 working days** for confirmed issues.

## Scope

This policy covers:
- The Python and XML code in this module
- The webhook controller endpoint
- The REST client logic and SSL handling

Out of scope:
- WooCommerce itself
- WordPress, the underlying web server, or any third-party plugin
- Odoo core code
- Misconfigurations of your own server (firewall, TLS, DNS, etc.)

## Security Practices Followed

- Webhook payloads are validated with HMAC-SHA256 against a per-instance
  secret. Invalid signatures return HTTP 401 with no information about
  whether the instance exists.
- Per-instance Consumer Key / Consumer Secret are stored in the database
  and access to the `digitalnatie.woo.instance` model is restricted to
  Odoo administrators via `ir.model.access.csv`.
- The HTTP client supports per-instance SSL verification. SSL is enabled
  by default and only documented to be disabled in development.
- No telemetry, no outbound calls to anything other than the
  Consumer-Key-protected WooCommerce REST endpoint configured by the
  administrator.
- No third-party SaaS dependency.
- Cron jobs commit/rollback per instance, so a poisoned instance cannot
  corrupt the others.
