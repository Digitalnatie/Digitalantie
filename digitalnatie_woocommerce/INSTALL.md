# Installation

## Requirements

- Odoo 18.0 Community (or Enterprise)
- Python `requests` package (already included with Odoo)
- A reachable WooCommerce store with REST API enabled

---

## 1. Copy the module

Drop the `digitalnatie_woocommerce` directory inside any folder declared
in your Odoo `addons_path` (usually `/mnt/extra-addons` for Docker
installations).

```bash
cp -r digitalnatie_woocommerce /mnt/extra-addons/
```

For Docker Compose:
```yaml
services:
  odoo:
    image: odoo:18.0
    volumes:
      - ./custom_addons:/mnt/extra-addons:rw
```

## 2. Update the apps list

In Odoo:
1. Activate **Developer Mode** (Settings → bottom of page → *Activate the
   developer mode*)
2. Apps → **Update Apps List** → *Update*

## 3. Install the module

Apps → search **WooCommerce Connector** → click **Install**.

## 4. (CLI alternative) Install from command line

```bash
docker compose exec odoo odoo \
    -c /etc/odoo/odoo.conf \
    --db_host=db --db_user=odoo --db_password=<your-pass> \
    -d <your-db> \
    -i digitalnatie_woocommerce \
    --stop-after-init
docker restart <your-odoo-container>
```

## 5. Generate WooCommerce REST API keys

In your WordPress admin:
1. **WooCommerce → Settings → Advanced → REST API**
2. **Add Key**
3. Description: `Odoo Connector`
4. Permissions: **Read/Write**
5. Generate and copy the **Consumer Key** and **Consumer Secret** (you
   will not be able to see the secret again).

## 6. Create your first instance in Odoo

1. **WooCommerce → Instances → New**
2. Fill in:
   - Name (any label)
   - API Base URL — for example `https://yourstore.com/wp-json/wc/v3/`
   - Consumer Key / Consumer Secret
   - Warehouse used for inventory sync
3. Save.
4. Click **Test Connection**. A success message confirms the link.

## 7. (Optional) Register webhooks for instant updates

On the instance form, click **Register Webhooks**. The module creates
order / product / customer webhooks in WooCommerce pointing back to this
Odoo instance, signed with a randomly generated secret.

> Webhooks require your Odoo `web.base.url` system parameter to be set
> to a URL reachable from WooCommerce.

## 8. (Optional) Activate cron jobs

Cron jobs ship **inactive** so that nothing runs unattended until you
opt-in.

1. Activate **Developer Mode**
2. **Settings → Technical → Scheduled Actions**
3. Search `WooCommerce:`
4. Open each cron you need (e.g. *Import Orders*) and tick **Active**

## Upgrading

```bash
docker compose exec odoo odoo \
    -c /etc/odoo/odoo.conf \
    --db_host=db --db_user=odoo --db_password=<your-pass> \
    -d <your-db> \
    -u digitalnatie_woocommerce \
    --stop-after-init
docker restart <your-odoo-container>
```

## Uninstalling

**Apps → WooCommerce Connector → Uninstall**.

Uninstalling removes the module's data tables (instances, logs, meta
mappings). Products and orders that were imported into Odoo remain.
