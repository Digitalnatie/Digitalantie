# Changelog

All notable changes to **WooCommerce Connector** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/)
inside the Odoo `18.0.MAJOR.MINOR.PATCH` convention.

---

## [18.0.3.0.0] — 2026-05-24

First public release on the Odoo Apps Store.

### Added
- Global settings page under **Settings → WooCommerce** with request
  timeout, pagination size, log retention and log level.
- Daily cron *Cleanup Old Sync Logs* (active by default) honouring the
  configured retention.
- `images` entry in the manifest for marketplace cover art.
- `OPL-1` license and `support@digitalnatie.be` support address.
- Full README, INSTALL, SECURITY and LICENSE documentation.

### Changed
- Manifest cleaned and Apps-Store-compliant (name, summary, author,
  website, license, price, currency, application=True).
- API request timeout now read from system parameter (was hard-coded
  to 90s).
- Pagination size now read from system parameter (was hard-coded
  to 100).

### Removed
- `.claude/` development workspace folder.
- Unused global credential fields on `res.config.settings` (credentials
  are per-instance, not global).

---

## [18.0.2.2.0] — Prior internal release

- Internal Digitalnatie release. Not published.

## [18.0.2.1.0] — Prior internal release

- Initial multi-instance, webhooks and meta-mapping architecture.
