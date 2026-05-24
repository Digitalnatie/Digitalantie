import base64
import hashlib
import hmac
import logging
import secrets

import requests
from requests.auth import HTTPBasicAuth

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DIRECTION_SELECTION = [
    ("disabled", "Disabled"),
    ("import", "Import only"),
    ("export", "Export only"),
    ("both", "Bi-directional"),
]

# WooCommerce webhook topics registered by action_register_webhooks().
WEBHOOK_TOPICS = [
    "order.created",
    "order.updated",
    "product.created",
    "product.updated",
    "customer.created",
]


class DigitalnatieWooInstance(models.Model):
    _name = "digitalnatie.woo.instance"
    _description = "Digitalnatie WooCommerce Instance"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    api_url = fields.Char(
        string="API Base URL",
        required=True,
        help="Base URL of the WooCommerce REST API, for example: "
        "https://yourshop.com/wp-json/wc/v3/",
    )
    consumer_key = fields.Char(string="Consumer Key", required=True)
    consumer_secret = fields.Char(string="Consumer Secret", required=True)
    is_active = fields.Boolean(string="Active", default=True)
    verify_ssl = fields.Boolean(
        string="Verify SSL",
        default=True,
        help="Disable only for development environments.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        help="Warehouse used as the source/target of inventory synchronisation.",
    )

    # --- Synchronisation direction configuration ---
    sync_product_direction = fields.Selection(
        DIRECTION_SELECTION, string="Products", default="both", required=True
    )
    sync_customer_direction = fields.Selection(
        [("disabled", "Disabled"), ("import", "Import only")],
        string="Customers",
        default="import",
        required=True,
    )
    sync_order_direction = fields.Selection(
        [("disabled", "Disabled"), ("import", "Import only")],
        string="Orders",
        default="import",
        required=True,
    )
    sync_inventory_direction = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("export", "Export only (Odoo → WooCommerce)"),
        ],
        string="Inventory Sync",
        default="export",
        required=True,
        help="Odoo is the single source of truth for inventory. Regular and "
        "scheduled syncs only push stock to WooCommerce. To pull stock back "
        "from WooCommerce, use the manual 'Import Stock (Recovery)' action.",
    )
    sync_price_direction = fields.Selection(
        [
            ("disabled", "Disabled"),
            ("export", "Export only (Odoo → WooCommerce)"),
        ],
        string="Price Sync",
        default="export",
        required=True,
        help="Odoo is the single source of truth for prices. Regular and "
        "scheduled syncs only push prices to WooCommerce. To pull prices back "
        "from WooCommerce, use the manual 'Import Prices (Recovery)' action.",
    )
    sync_fulfillment_direction = fields.Selection(
        DIRECTION_SELECTION, string="Fulfillment Status", default="both", required=True
    )
    import_only_completed_orders = fields.Boolean(
        string="Import Only Completed Orders",
        default=False,
        help="When enabled, only orders with WooCommerce status 'completed' are imported.",
    )
    confirm_imported_orders = fields.Boolean(
        string="Confirm Imported Orders",
        default=False,
        help="Automatically confirm imported orders whose WooCommerce status is "
        "'processing' or 'completed'.",
    )

    # --- Webhooks ---
    webhook_enabled = fields.Boolean(string="Webhooks Enabled", default=False)
    webhook_secret = fields.Char(
        string="Webhook Secret",
        copy=False,
        help="Shared secret used to verify the signature of incoming WooCommerce webhooks.",
    )
    webhook_url = fields.Char(
        string="Webhook Delivery URL",
        compute="_compute_webhook_url",
        help="Configure this URL in WooCommerce, or use 'Register Webhooks'.",
    )

    last_sync_products = fields.Datetime(string="Last Products Sync", readonly=True)
    last_sync_orders = fields.Datetime(string="Last Orders Sync", readonly=True)
    last_sync_customers = fields.Datetime(string="Last Customers Sync", readonly=True)
    last_sync_stock = fields.Datetime(string="Last Inventory Sync", readonly=True)
    last_sync_prices = fields.Datetime(string="Last Price Sync", readonly=True)

    meta_mapping_ids = fields.One2many(
        "digitalnatie.woo.meta.mapping", "instance_id", string="Meta Field Mappings"
    )
    log_ids = fields.One2many(
        "digitalnatie.woo.log", "instance_id", string="Sync Logs"
    )
    log_count = fields.Integer(string="Log Count", compute="_compute_log_count")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    def _compute_webhook_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for instance in self:
            if isinstance(instance.id, int):
                instance.webhook_url = "%s/digitalnatie_woo/webhook/%s" % (
                    (base_url or "").rstrip("/"),
                    instance.id,
                )
            else:
                instance.webhook_url = False

    def _compute_log_count(self):
        log_data = self.env["digitalnatie.woo.log"].read_group(
            [("instance_id", "in", self.ids)], ["instance_id"], ["instance_id"]
        )
        counts = {d["instance_id"][0]: d["instance_id_count"] for d in log_data}
        for instance in self:
            instance.log_count = counts.get(instance.id, 0)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _woo_log(
        self,
        operation,
        level,
        summary,
        message=False,
        woo_ref=False,
        res_model=False,
        res_id=False,
    ):
        """Create a sync log line. Safe to call from public webhook context."""
        self.ensure_one()
        try:
            self.env["digitalnatie.woo.log"].sudo().create(
                {
                    "instance_id": self.id,
                    "operation": operation,
                    "level": level,
                    "summary": (summary or "")[:255],
                    "message": message,
                    "woo_ref": woo_ref and str(woo_ref) or False,
                    "res_model": res_model,
                    "res_id": res_id,
                }
            )
        except Exception:  # logging must never break a sync
            _logger.exception("Digitalnatie Woo: failed to write sync log")

    # ------------------------------------------------------------------
    # Direction helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _direction_allows(direction, way):
        """way is 'import' or 'export'."""
        return direction == "both" or direction == way

    # ------------------------------------------------------------------
    # REST API client
    # ------------------------------------------------------------------
    def _get_session(self):
        self.ensure_one()
        if not self.api_url or not self.consumer_key or not self.consumer_secret:
            raise UserError(_("WooCommerce credentials are not fully configured."))
        session = requests.Session()
        session.auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        session.headers.update({"Accept": "application/json"})
        session.verify = self.verify_ssl
        return session

    def _wc_url(self, endpoint):
        return self.api_url.rstrip("/") + "/" + str(endpoint).lstrip("/")

    def _get_timeout(self):
        """Read the global request timeout (in seconds) from system parameters."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'digitalnatie_woocommerce.request_timeout', '90'
        )
        try:
            return max(int(param), 5)
        except (TypeError, ValueError):
            return 90

    def _get_page_size(self):
        """Read the global pagination size from system parameters."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'digitalnatie_woocommerce.page_size', '100'
        )
        try:
            return max(min(int(param), 100), 1)
        except (TypeError, ValueError):
            return 100

    def _wc_call(self, method, endpoint, params=None, payload=None):
        """Perform a single WooCommerce REST call. Returns (json, response)."""
        self.ensure_one()
        session = self._get_session()
        url = self._wc_url(endpoint)
        _logger.info("WooCommerce Connector: %s %s params=%s", method, url, params)
        try:
            response = session.request(
                method, url, params=params, json=payload,
                timeout=self._get_timeout(),
            )
        except Exception as e:
            raise UserError(_("Error connecting to WooCommerce: %s") % e)

        if response.status_code >= 400:
            preview = response.text[:500] if response.text else "(empty body)"
            raise UserError(
                _("WooCommerce API error %s on %s %s:\n%s")
                % (response.status_code, method, endpoint, preview)
            )

        if not response.text or not response.text.strip():
            return {}, response

        try:
            return response.json(), response
        except Exception as e:
            preview = response.text[:300]
            raise UserError(
                _("Invalid JSON from WooCommerce (HTTP %s): %s\nBody: %s")
                % (response.status_code, e, preview)
            )

    def _wc_get(self, endpoint, params=None):
        data, _resp = self._wc_call("GET", endpoint, params=params)
        return data

    def _wc_post(self, endpoint, payload):
        data, _resp = self._wc_call("POST", endpoint, payload=payload)
        return data

    def _wc_put(self, endpoint, payload):
        data, _resp = self._wc_call("PUT", endpoint, payload=payload)
        return data

    def _wc_iter(self, endpoint, params=None, per_page=None):
        """Yield records from a WooCommerce collection, page by page."""
        self.ensure_one()
        if per_page is None:
            per_page = self._get_page_size()
        page = 1
        params = dict(params or {})
        while True:
            params.update({"per_page": per_page, "page": page})
            batch = self._wc_get(endpoint, params=params)
            if not batch:
                break
            for record in batch:
                yield record
            if len(batch) < per_page:
                break
            page += 1

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------
    def action_test_connection(self):
        for instance in self:
            instance._test_connection_single()
        return True

    def _test_connection_single(self):
        self.ensure_one()
        products = self._wc_get("products", params={"per_page": 1, "page": 1})
        self._woo_log(
            "connection", "info", _("Connection test succeeded"),
            message=_("Reachable, returned %s product(s).") % len(products),
        )
        raise UserError(
            _("Connection successful! WooCommerce returned %s product(s).")
            % len(products)
        )

    # ------------------------------------------------------------------
    # Meta / custom field helpers (shared by import & export)
    # ------------------------------------------------------------------
    def _apply_meta_data(self, record, woo_object, meta_list):
        """Store raw meta_data on the record and apply configured import mappings."""
        self.ensure_one()
        meta = {
            m.get("key"): m.get("value")
            for m in (meta_list or [])
            if isinstance(m, dict) and m.get("key")
        }
        if "woo_meta_data" in record._fields:
            record.woo_meta_data = meta
        mappings = self.meta_mapping_ids.filtered(
            lambda m: m.woo_object == woo_object
            and m.direction in ("import", "both")
            and m.active
        )
        for mapping in mappings:
            key = mapping.woo_meta_key
            field = mapping.odoo_field_name
            if key in meta and field in record._fields:
                try:
                    record.write({field: meta[key]})
                except Exception as e:
                    _logger.warning(
                        "Digitalnatie Woo: meta mapping %s -> %s failed: %s",
                        key, field, e,
                    )

    def _build_meta_export(self, record, woo_object):
        """Build a WooCommerce 'meta_data' payload from configured export mappings."""
        self.ensure_one()
        mappings = self.meta_mapping_ids.filtered(
            lambda m: m.woo_object == woo_object
            and m.direction in ("export", "both")
            and m.active
        )
        payload = []
        for mapping in mappings:
            field = mapping.odoo_field_name
            if field in record._fields:
                value = record[field]
                if hasattr(value, "ids"):  # relational field
                    value = value.ids
                payload.append({"key": mapping.woo_meta_key, "value": value})
        return payload

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------
    def action_register_webhooks(self):
        """Create the webhooks inside WooCommerce that point back to this Odoo."""
        for instance in self:
            instance._register_webhooks_single()
        return True

    def _register_webhooks_single(self):
        self.ensure_one()
        if not self.webhook_secret:
            self.webhook_secret = secrets.token_hex(24)
        delivery_url = self.webhook_url
        if not delivery_url or delivery_url.startswith("False"):
            raise UserError(
                _("The Odoo base URL ('web.base.url') is not configured, so the "
                  "webhook delivery URL cannot be built.")
            )
        existing = self._wc_get("webhooks", params={"per_page": 100})
        existing_urls = {
            (w.get("topic"), w.get("delivery_url")) for w in (existing or [])
        }
        created = 0
        for topic in WEBHOOK_TOPICS:
            if (topic, delivery_url) in existing_urls:
                continue
            self._wc_post(
                "webhooks",
                {
                    "name": "Odoo Digitalnatie - %s" % topic,
                    "topic": topic,
                    "delivery_url": delivery_url,
                    "secret": self.webhook_secret,
                    "status": "active",
                },
            )
            created += 1
        self.webhook_enabled = True
        self._woo_log(
            "webhook", "info", _("Registered %s webhook(s)") % created,
            message=_("Delivery URL: %s") % delivery_url,
        )
        raise UserError(
            _("%s WooCommerce webhook(s) registered for this instance.") % created
        )

    def _verify_webhook_signature(self, raw_body, signature):
        self.ensure_one()
        if not self.webhook_secret:
            # No secret configured: accept but warn.
            return True
        expected = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
            ).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature or "")

    def _handle_webhook(self, topic, payload):
        """Dispatch an incoming webhook to the right single-record import."""
        self.ensure_one()
        resource = (topic or "").split(".")[0]
        woo_id = payload.get("id")
        if not woo_id:
            self._woo_log("webhook", "warning", _("Webhook %s without id") % topic)
            return
        if resource == "order" and self.sync_order_direction != "disabled":
            self._import_one_order(woo_id)
        elif resource == "product" and self._direction_allows(
            self.sync_product_direction, "import"
        ):
            self._import_one_product(woo_id)
        elif resource == "customer" and self.sync_customer_direction != "disabled":
            self._import_one_customer(woo_id)
        else:
            self._woo_log(
                "webhook", "info", _("Webhook %s ignored (sync disabled)") % topic,
                woo_ref=woo_id,
            )
            return
        self._woo_log(
            "webhook", "info", _("Webhook %s processed") % topic, woo_ref=woo_id
        )

    # ------------------------------------------------------------------
    # Orchestration buttons
    # ------------------------------------------------------------------
    def action_import_products(self):
        for instance in self:
            instance.import_products()
        return True

    def action_export_products(self):
        for instance in self:
            instance.export_products()
        return True

    def action_import_customers(self):
        for instance in self:
            instance.import_customers()
        return True

    def action_import_orders(self):
        for instance in self:
            instance.import_orders()
        return True

    def action_sync_inventory(self):
        for instance in self:
            instance.sync_inventory()
        return True

    def action_link_products(self):
        for instance in self:
            instance.link_products()
        return True

    def action_import_inventory_recovery(self):
        for instance in self:
            instance.import_inventory()
        return True

    def action_import_prices_recovery(self):
        for instance in self:
            instance.import_prices()
        return True

    def action_sync_prices(self):
        for instance in self:
            instance.sync_prices()
        return True

    def action_sync_fulfillment(self):
        for instance in self:
            instance.sync_fulfillment()
        return True

    def action_full_sync(self):
        for instance in self:
            if instance._direction_allows(instance.sync_product_direction, "import"):
                instance.import_products()
            if instance.sync_customer_direction != "disabled":
                instance.import_customers()
            if instance.sync_order_direction != "disabled":
                instance.import_orders()
            instance.sync_inventory()
            instance.sync_prices()
            instance.sync_fulfillment()
        return True

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("WooCommerce Sync Logs"),
            "res_model": "digitalnatie.woo.log",
            "view_mode": "list,form",
            "domain": [("instance_id", "=", self.id)],
            "context": {"default_instance_id": self.id},
        }

    # --- Bi-directional orchestration ---------------------------------
    def sync_inventory(self):
        """Regular inventory sync. Odoo is authoritative: export only.

        WooCommerce -> Odoo stock import is intentionally NOT performed here so
        that scheduled or repeated syncs can never overwrite Odoo stock. Use
        ``import_inventory`` (manual recovery) or ``link_products`` instead.
        """
        self.ensure_one()
        if self.sync_inventory_direction == "disabled":
            return
        self.export_inventory()

    def sync_prices(self):
        """Regular price sync. Odoo is authoritative: export only.

        WooCommerce -> Odoo price import is intentionally NOT performed here so
        that scheduled or repeated syncs can never overwrite Odoo prices. Use
        ``import_prices`` (manual recovery) instead.
        """
        self.ensure_one()
        if self.sync_price_direction == "disabled":
            return
        self.export_prices()

    def sync_fulfillment(self):
        self.ensure_one()
        direction = self.sync_fulfillment_direction
        if self._direction_allows(direction, "import"):
            self.import_fulfillment()
        if self._direction_allows(direction, "export"):
            self.export_order_statuses()

    # ------------------------------------------------------------------
    # Scheduled actions
    # ------------------------------------------------------------------
    @api.model
    def _cron_run(self, method_name, predicate=None):
        instances = self.search([("is_active", "=", True)])
        for instance in instances:
            if predicate and not predicate(instance):
                continue
            try:
                getattr(instance, method_name)()
                self.env.cr.commit()
            except Exception as e:
                self.env.cr.rollback()
                _logger.exception("Digitalnatie Woo: cron %s failed: %s", method_name, e)
                instance._woo_log("other", "error", _("Cron %s failed") % method_name,
                                   message=str(e))
                self.env.cr.commit()

    @api.model
    def cron_import_orders(self):
        self._cron_run(
            "import_orders",
            predicate=lambda i: i.sync_order_direction != "disabled",
        )

    @api.model
    def cron_import_products(self):
        self._cron_run(
            "import_products",
            predicate=lambda i: i._direction_allows(i.sync_product_direction, "import"),
        )

    @api.model
    def cron_sync_inventory(self):
        self._cron_run(
            "sync_inventory",
            predicate=lambda i: i.sync_inventory_direction != "disabled",
        )

    @api.model
    def cron_sync_prices(self):
        self._cron_run(
            "sync_prices",
            predicate=lambda i: i.sync_price_direction != "disabled",
        )

    @api.model
    def cron_sync_fulfillment(self):
        self._cron_run(
            "sync_fulfillment",
            predicate=lambda i: i.sync_fulfillment_direction != "disabled",
        )

    # ------------------------------------------------------------------
    # Shared record helpers
    # ------------------------------------------------------------------
    def _get_stock_location(self):
        self.ensure_one()
        warehouse = self.warehouse_id
        if not warehouse:
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", self.company_id.id)], limit=1
            )
        return warehouse.lot_stock_id if warehouse else False

    def _set_product_stock(self, variant, qty):
        """Set the on-hand quantity of a variant at the instance warehouse."""
        self.ensure_one()
        if not variant or not variant.is_storable:
            return
        location = self._get_stock_location()
        if not location:
            return
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            return
        Quant = self.env["stock.quant"].sudo().with_context(inventory_mode=True)
        quant = Quant.search(
            [("product_id", "=", variant.id), ("location_id", "=", location.id)],
            limit=1,
        )
        if quant:
            quant.inventory_quantity = qty
        else:
            quant = Quant.create(
                {
                    "product_id": variant.id,
                    "location_id": location.id,
                    "inventory_quantity": qty,
                }
            )
        quant.action_apply_inventory()

    def _woo_image_to_base64(self, url):
        """Download an image URL and return base64 bytes, or False on failure."""
        if not url:
            return False
        try:
            response = requests.get(url, timeout=60, verify=self.verify_ssl)
            if response.status_code == 200 and response.content:
                return base64.b64encode(response.content)
        except Exception as e:
            _logger.warning("Digitalnatie Woo: could not download image %s: %s", url, e)
        return False
