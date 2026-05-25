# WooCommerce Connector for Odoo 18

**Bi-directional WooCommerce ↔ Odoo 18 sync — multi-instance, webhooks, custom field mapping.**

![Odoo 18.0](https://img.shields.io/badge/Odoo-18.0%20Community-714B67?logo=odoo&logoColor=white)
![WooCommerce](https://img.shields.io/badge/WooCommerce-REST%20v3-96588A?logo=woocommerce&logoColor=white)
![License](https://img.shields.io/badge/License-OPL--1-blue)
![Price](https://img.shields.io/badge/Price-%E2%82%AC199-green)

---

Connect one or several WooCommerce stores to your Odoo 18 Community database and keep products, customers, orders, inventory and prices in sync — without external SaaS, without telemetry, without activation keys.

## What syncs

| Direction | Objects |
|-----------|---------|
| WooCommerce → Odoo | Products & variants, Customers, Orders, Stock recovery (manual), Price recovery (manual), Custom meta fields |
| Odoo → WooCommerce | Products, prices, images, Stock levels, Fulfillment status, Custom field values, Refunds |

## Key features

- **Bi-directional, per-object direction control** — disabled / import / export / both
- **Instant webhooks** — HMAC-SHA256 signed, one-click registration
- **Multi-instance** — connect as many WooCommerce stores as you need
- **Refund wizard** — full and partial WooCommerce refunds from Odoo
- **Custom field mapping** — map any `meta_data` key to any Odoo field
- **Full sync logs** — every operation logged with level, WC reference and Odoo target
- **No SaaS** — fully self-contained, no phone-home, no activation key

## Requirements

- Odoo 18.0 Community (or Enterprise)
- Python `requests` library (ships with Odoo)
- A WooCommerce store with REST API enabled (WooCommerce 3.5+)

## Quick install

1. Copy `digitalnatie_woocommerce/` into your Odoo `addons_path`
2. Apps → **Update Apps List** → install **WooCommerce Connector**
3. WooCommerce → Instances → **New** → enter URL + keys → **Test Connection**

See [`digitalnatie_woocommerce/INSTALL.md`](digitalnatie_woocommerce/INSTALL.md) for the full step-by-step guide.

## Cron jobs

All inactive by default — enable what you need:

| Job | Frequency |
|-----|-----------|
| Import Orders | Every 15 min |
| Import Products | Every 6 hours |
| Export Inventory | Every 30 min |
| Export Prices | Every 6 hours |
| Sync Fulfillment Status | Every 30 min |
| **Cleanup Old Sync Logs** | **Daily (active)** |

## Security

- Webhook payloads validated with HMAC-SHA256 per-instance secret
- Consumer Key / Secret stored in DB, restricted to Odoo administrators
- SSL verification on by default
- Zero telemetry, zero outbound calls except to your configured WooCommerce endpoint

See [`digitalnatie_woocommerce/SECURITY.md`](digitalnatie_woocommerce/SECURITY.md) for the disclosure policy.

## Support

- **Email:** support@digitalnatie.be
- **Website:** https://digitalnatie.be

## License

OPL-1 — see [`digitalnatie_woocommerce/LICENSE`](digitalnatie_woocommerce/LICENSE) for the full text.

## Changelog

See [`digitalnatie_woocommerce/CHANGELOG.md`](digitalnatie_woocommerce/CHANGELOG.md).

---

*Odoo® is a registered trademark of Odoo S.A. WooCommerce® is a registered trademark of Automattic Inc.*
