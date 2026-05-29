# WooCommerce Connector
<img width="1693" height="929" alt="image" src="https://github.com/user-attachments/assets/d1ddfbf9-38a2-40e3-a64d-7075526167e4" />

**Bi-directional WooCommerce ↔ Odoo 18 connector — multi-instance, webhooks, custom field mapping.**

Connect one or several WooCommerce stores to your Odoo 18 Community database
and keep products, customers, orders, inventory and prices in sync — without
external SaaS, without telemetry, without activation keys.

---
<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/0b6aaa81-b3b0-4b0a-88b8-030d61367cb6" />
<img width="1710" height="381" alt="image" src="https://github.com/user-attachments/assets/7884633c-8ca3-4d54-8f1d-13d6bf6753dc" />
<img width="1731" height="354" alt="image" src="https://github.com/user-attachments/assets/b1825fbd-e505-4fea-9777-a8c8a803e4e2" />
<img width="1660" height="349" alt="image" src="https://github.com/user-attachments/assets/d6da186f-f488-48a5-8542-b970bca2127d" />



## Features

### WooCommerce → Odoo (Import)
- Products and variants (with categories, images, tags, taxes)
- Customers (billing/shipping addresses, contact info)
- Orders (with shipping lines, fees, discounts, taxes, attendees)
- Stock recovery import (manual, on-demand)
- Price recovery import (manual, on-demand)
- Custom WooCommerce meta fields mapped to Odoo fields

### Odoo → WooCommerce (Export)
- Products and variants (descriptions, images, prices, publication state)
- Stock levels (Odoo is the single source of truth)
- Order fulfillment status updates
- Custom Odoo field values written to WooCommerce meta_data
<img width="1578" height="903" alt="image" src="https://github.com/user-attachments/assets/d45bc995-4349-43b8-b079-424a3496ba1e" />

### Real-time updates
- Signed WooCommerce webhooks for instant order, product and customer
  notifications
- One-click webhook registration from the instance form

### Operations
- Multi-instance: connect as many stores as you need
- Per-instance, per-object direction control
  (disabled / import / export / bi-directional)
- Scheduled cron jobs (disabled by default — enable per your workload)
- Sync log with operation, level, WooCommerce reference and Odoo target
- Refund wizard (full and partial WooCommerce refunds from Odoo)
- Connection test button
- Automatic log cleanup (configurable retention)

### Safety
- Stock and prices flow Odoo → WooCommerce in scheduled syncs (Odoo is
  authoritative). Recovery imports are explicit, separate actions guarded
  by a confirmation dialog.
- Configurable per-store SSL verification
- Per-cron error isolation: a failing store never blocks the others

---

## Requirements

- Odoo 18.0 Community
- Python `requests` library (shipped with Odoo)
- A WooCommerce store with REST API enabled

---

## Installation

See [INSTALL.md](INSTALL.md) for full step-by-step instructions.

Short version:
1. Copy the `digitalnatie_woocommerce` folder into your Odoo `addons` path
2. Update the apps list (Apps → Update Apps List)
3. Install **WooCommerce Connector**

---

## Configuration

### 1. WooCommerce side — generate REST API keys
1. WooCommerce → Settings → Advanced → REST API → **Add Key**
2. Permission: **Read/Write**
3. Copy the Consumer Key and Consumer Secret

### 2. Odoo side — connect your store
1. WooCommerce → Instances → **New**
2. Fill in:
   - **Name**: any label
   - **API Base URL**: `https://yourstore.com/wp-json/wc/v3/`
   - **Consumer Key** and **Consumer Secret**
   - **Warehouse**: the warehouse used for inventory sync
3. Click **Test Connection**
4. Choose the sync direction per object on the **Sync Settings** tab

### 3. Webhooks (optional, recommended for instant updates)
On the instance form, click **Register Webhooks**. The module creates
order/product/customer webhooks in WooCommerce, pointing back to a unique
URL on your Odoo instance, signed with a random secret.

### 4. Global defaults
**Settings → WooCommerce**:
- Request timeout (default 90s)
- Pagination size (default 100)
- Log retention (default 30 days)
- Log level (default Info)

---

## Sync flow

| Object       | Direction (default)      | Triggered by                              |
|--------------|--------------------------|-------------------------------------------|
| Products     | Bi-directional           | Cron (off by default), button, webhook    |
| Customers    | Import only              | Cron (off by default), button, webhook    |
| Orders       | Import only              | Cron (off by default), button, webhook    |
| Inventory    | Export (Odoo → Woo)      | Cron (off by default), button             |
| Prices       | Export (Odoo → Woo)      | Cron (off by default), button             |
| Fulfillment  | Bi-directional           | Cron (off by default), button             |

To activate a cron: **Settings → Technical → Scheduled Actions →
WooCommerce: …** and tick *Active*.

---

## Cron jobs

The module ships with these cron jobs (all **inactive** by default — enable
the ones you need):

| Name                                  | Default frequency |
|---------------------------------------|-------------------|
| Import Orders                         | every 15 minutes  |
| Import Products                       | every 6 hours     |
| Export Inventory (Odoo → WooCommerce) | every 30 minutes  |
| Export Prices (Odoo → WooCommerce)    | every 6 hours     |
| Sync Fulfillment Status               | every 30 minutes  |
| Cleanup Old Sync Logs                 | daily (active)    |

Each cron iterates over every active instance and isolates errors so that
one failing store does not block the others.

---

## FAQ

**Does this overwrite Odoo stock with WooCommerce stock?**
No. Scheduled and manual *Export Inventory* always pushes Odoo → Woo. To
import stock from WooCommerce (one-off, e.g. after a Woo-only adjustment),
use **Import Stock (Recovery)** — it is gated by a confirmation dialog.

**Can I connect multiple WooCommerce stores?**
Yes. Create one instance record per store. Each cron iterates over all
active instances.

**Does this require an internet activation server?**
No. The module is fully self-contained. No telemetry, no SaaS, no key
server.

**Which WooCommerce versions are supported?**
Any version exposing the `wc/v3` REST API (WooCommerce 3.5+).

---

## Troubleshooting

| Symptom                                  | Where to look                                |
|------------------------------------------|----------------------------------------------|
| Connection test fails                    | Instance form → check URL and keys, click Test Connection |
| Webhook not firing                       | WooCommerce → Settings → Advanced → Webhooks → Delivery log |
| Sync error                               | WooCommerce → Sync Logs (filter by Level = Error) |
| SSL error on staging WooCommerce         | Instance form → uncheck **Verify SSL** (dev only) |
| Cron not running                         | Settings → Technical → Scheduled Actions → activate it |
| Log table growing                        | Settings → WooCommerce → reduce Log Retention |

---

## Security

- Per-store credentials are stored in the database (Consumer Key/Secret).
  Restrict access to the `digitalnatie.woo.instance` model to administrators.
- Webhooks are validated with HMAC-SHA256 against the per-instance secret.
- Public webhook endpoint requires a valid signature; invalid signatures
  return HTTP 401 without revealing whether the instance exists.

See [SECURITY.md](SECURITY.md) for disclosure policy.

---

## Support

- Email: **support@digitalnatie.be**
- Website: [https://digitalnatie.be](https://digitalnatie.be)

## License

OPL-1 — see [LICENSE](LICENSE) for the full text.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
