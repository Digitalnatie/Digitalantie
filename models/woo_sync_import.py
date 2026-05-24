import logging

from odoo import fields, models, _
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

FULFILLMENT_MAP = {
    "pending": "pending",
    "on-hold": "pending",
    "processing": "processing",
    "completed": "fulfilled",
    "cancelled": "cancelled",
    "failed": "cancelled",
    "refunded": "refunded",
}

WOO_SERVICE_PRODUCTS = {
    "delivery": "WooCommerce Delivery",
    "fee": "WooCommerce Fee",
    "tax": "WooCommerce Taxes",
    "discount": "WooCommerce Discount",
}


class DigitalnatieWooInstanceImport(models.Model):
    _inherit = "digitalnatie.woo.instance"

    # ------------------------------------------------------------------
    # Small value helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _to_float(value):
        if value in (None, "", False):
            return 0.0
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_woo_datetime(value):
        """Parse a WooCommerce GMT datetime string into a naive UTC datetime."""
        if not value:
            return False
        text = str(value).replace("T", " ")
        for sep in (".", "+"):
            if sep in text:
                text = text.split(sep)[0]
        text = text.strip()
        try:
            return fields.Datetime.to_datetime(text)
        except Exception:
            return False

    @staticmethod
    def _map_fulfillment(status):
        return FULFILLMENT_MAP.get(status)

    # ------------------------------------------------------------------
    # Reference data (categories, tags, attributes)
    # ------------------------------------------------------------------
    def _get_or_create_category(self, woo_cat):
        Categ = self.env["product.category"]
        woo_id = woo_cat.get("id")
        name = woo_cat.get("name")
        categ = False
        if woo_id:
            categ = Categ.search([("woo_category_id", "=", woo_id)], limit=1)
        if not categ and name:
            categ = Categ.search([("name", "=", name)], limit=1)
        if categ:
            if woo_id and not categ.woo_category_id:
                categ.woo_category_id = woo_id
            return categ
        if not name:
            return False
        return Categ.create({"name": name, "woo_category_id": woo_id or False})

    def _get_or_create_product_tag(self, woo_tag):
        Tag = self.env["product.tag"]
        woo_id = woo_tag.get("id")
        name = woo_tag.get("name")
        tag = False
        if woo_id:
            tag = Tag.search([("woo_tag_id", "=", woo_id)], limit=1)
        if not tag and name:
            tag = Tag.search([("name", "=", name)], limit=1)
        if tag:
            if woo_id and not tag.woo_tag_id:
                tag.woo_tag_id = woo_id
            return tag
        if not name:
            return False
        return Tag.create({"name": name, "woo_tag_id": woo_id or False})

    def _get_or_create_partner_category(self, name):
        Categ = self.env["res.partner.category"]
        name = (name or "").strip()
        categ = Categ.search([("name", "=", name)], limit=1)
        if not categ:
            categ = Categ.create({"name": name})
        return categ

    def _get_or_create_attribute(self, name):
        Attr = self.env["product.attribute"]
        name = (name or "Attribute").strip()
        attr = Attr.search([("name", "=", name)], limit=1)
        if not attr:
            attr = Attr.create({"name": name, "create_variant": "always"})
        return attr

    def _get_or_create_attr_value(self, attribute, name):
        Value = self.env["product.attribute.value"]
        name = (name or "").strip()
        value = Value.search(
            [("attribute_id", "=", attribute.id), ("name", "=", name)], limit=1
        )
        if not value:
            value = Value.create({"attribute_id": attribute.id, "name": name})
        return value

    def _get_woo_service_product(self, key):
        """Lazily create the service products used for order charges."""
        Product = self.env["product.product"]
        ref = "WOO-%s" % key.upper()
        product = Product.search([("default_code", "=", ref)], limit=1)
        if not product:
            product = Product.create(
                {
                    "name": WOO_SERVICE_PRODUCTS.get(key, "WooCommerce Charge"),
                    "default_code": ref,
                    "type": "service",
                    "invoice_policy": "order",
                    "sale_ok": True,
                    "purchase_ok": False,
                    "list_price": 0.0,
                    "taxes_id": [(5, 0, 0)],
                }
            )
        return product

    # ------------------------------------------------------------------
    # PRODUCTS
    # ------------------------------------------------------------------
    def import_products(self):
        self.ensure_one()
        count = 0
        for wp in self._wc_iter("products"):
            try:
                with self.env.cr.savepoint():
                    self._import_single_product(wp)
                count += 1
            except Exception as e:
                self._woo_log(
                    "import_product", "error",
                    _("Failed to import product %s") % wp.get("id"),
                    message=str(e), woo_ref=wp.get("id"),
                )
        self.last_sync_products = fields.Datetime.now()
        self._woo_log(
            "import_product", "info",
            _("Imported / updated %s product(s)") % count,
        )
        return count

    def _import_one_product(self, woo_id):
        self.ensure_one()
        wp = self._wc_get("products/%s" % woo_id)
        if wp:
            return self._import_single_product(wp)
        return False

    def _import_single_product(self, wp):
        self.ensure_one()
        ProductTmpl = self.env["product.template"]
        woo_id = wp.get("id")
        sku = wp.get("sku") or False
        name = wp.get("name") or (_("Woo Product %s") % woo_id)

        domain = [("woo_product_id", "=", woo_id)]
        if sku:
            domain = ["|", ("woo_product_id", "=", woo_id), ("default_code", "=", sku)]
        product = ProductTmpl.search(domain, limit=1)

        vals = {
            "name": name,
            "woo_product_id": woo_id,
            "woo_instance_id": self.id,
            "sale_ok": True,
            "woo_published": wp.get("status") == "publish",
            "woo_last_import": fields.Datetime.now(),
        }
        if sku:
            vals["default_code"] = sku

        description = wp.get("short_description") or wp.get("description")
        if description:
            vals["description_sale"] = html2plaintext(description)

        weight = wp.get("weight")
        if weight not in (None, "", False):
            vals["weight"] = self._to_float(weight)

        price = wp.get("regular_price") or wp.get("price")
        if price not in (None, "", False):
            vals["list_price"] = self._to_float(price)

        categories = wp.get("categories") or []
        if categories:
            categ = self._get_or_create_category(categories[0])
            if categ:
                vals["categ_id"] = categ.id

        tag_ids = []
        for wt in wp.get("tags") or []:
            tag = self._get_or_create_product_tag(wt)
            if tag:
                tag_ids.append(tag.id)
        if tag_ids:
            vals["product_tag_ids"] = [(6, 0, tag_ids)]

        if wp.get("manage_stock"):
            vals["is_storable"] = True

        images = wp.get("images") or []
        if images and images[0].get("src"):
            vals["woo_image_url"] = images[0].get("src")

        if product:
            product.write(vals)
        else:
            product = ProductTmpl.create(vals)

        if images and images[0].get("src"):
            image_data = self._woo_image_to_base64(images[0].get("src"))
            if image_data:
                product.image_1920 = image_data

        is_variable = (wp.get("type") or "simple") == "variable"
        if (
            not is_variable
            and wp.get("manage_stock")
            and wp.get("stock_quantity") is not None
        ):
            self._set_product_stock(
                product.product_variant_id, wp.get("stock_quantity")
            )

        self._apply_meta_data(product, "product", wp.get("meta_data"))

        if is_variable:
            self._import_product_variants(product, wp)

        return product

    def _import_product_variants(self, product, wp):
        self.ensure_one()
        variations = list(self._wc_iter("products/%s/variations" % wp.get("id")))
        if not variations:
            return
        if not product.attribute_line_ids:
            attr_line_cmds = []
            for attr in wp.get("attributes") or []:
                if not attr.get("variation"):
                    continue
                attribute = self._get_or_create_attribute(attr.get("name"))
                value_ids = [
                    self._get_or_create_attr_value(attribute, opt).id
                    for opt in (attr.get("options") or [])
                    if opt
                ]
                if value_ids:
                    attr_line_cmds.append(
                        (0, 0, {
                            "attribute_id": attribute.id,
                            "value_ids": [(6, 0, value_ids)],
                        })
                    )
            if attr_line_cmds:
                product.write({"attribute_line_ids": attr_line_cmds})
        for wv in variations:
            self._map_single_variation(product, wv)

    def _map_single_variation(self, product, wv):
        var_id = wv.get("id")
        woo_attrs = {}
        for a in wv.get("attributes") or []:
            attr_name = (a.get("name") or "").strip().lower()
            option = (a.get("option") or "").strip().lower()
            if attr_name and option:
                woo_attrs[attr_name] = option

        variant = product.product_variant_ids.filtered(
            lambda v: var_id and v.woo_variation_id == var_id
        )[:1]
        if not variant and woo_attrs:
            for candidate in product.product_variant_ids:
                odoo_attrs = {
                    (ptav.attribute_id.name or "").strip().lower():
                        (ptav.name or "").strip().lower()
                    for ptav in candidate.product_template_variant_value_ids
                }
                if all(odoo_attrs.get(k) == v for k, v in woo_attrs.items()):
                    variant = candidate
                    break
        if not variant:
            return

        var_vals = {"woo_variation_id": var_id}
        if wv.get("sku"):
            var_vals["default_code"] = wv.get("sku")
        variant.write(var_vals)

        price = wv.get("regular_price") or wv.get("price")
        if price not in (None, "", False):
            try:
                variant.lst_price = self._to_float(price)
            except Exception:
                pass

        if wv.get("manage_stock") and wv.get("stock_quantity") is not None:
            self._set_product_stock(variant, wv.get("stock_quantity"))

        image_src = (wv.get("image") or {}).get("src")
        if image_src:
            image_data = self._woo_image_to_base64(image_src)
            if image_data:
                variant.image_1920 = image_data

        self._apply_meta_data(variant, "variant", wv.get("meta_data"))

    # ------------------------------------------------------------------
    # CUSTOMERS
    # ------------------------------------------------------------------
    def import_customers(self):
        self.ensure_one()
        count = 0
        for wc in self._wc_iter("customers"):
            try:
                with self.env.cr.savepoint():
                    self._import_single_customer(wc)
                count += 1
            except Exception as e:
                self._woo_log(
                    "import_customer", "error",
                    _("Failed to import customer %s") % wc.get("id"),
                    message=str(e), woo_ref=wc.get("id"),
                )
        self.last_sync_customers = fields.Datetime.now()
        self._woo_log(
            "import_customer", "info",
            _("Imported / updated %s customer(s)") % count,
        )
        return count

    def _import_one_customer(self, woo_id):
        self.ensure_one()
        wc = self._wc_get("customers/%s" % woo_id)
        if wc:
            return self._import_single_customer(wc)
        return False

    def _fill_partner_address(self, vals, addr):
        if not addr:
            return
        if addr.get("address_1"):
            vals["street"] = addr.get("address_1")
        if addr.get("address_2"):
            vals["street2"] = addr.get("address_2")
        if addr.get("city"):
            vals["city"] = addr.get("city")
        if addr.get("postcode"):
            vals["zip"] = addr.get("postcode")
        if addr.get("phone"):
            vals["phone"] = addr.get("phone")
        country = False
        if addr.get("country"):
            country = self.env["res.country"].search(
                [("code", "=", addr.get("country"))], limit=1
            )
            if country:
                vals["country_id"] = country.id
        if addr.get("state") and country:
            state = self.env["res.country.state"].search(
                [
                    ("country_id", "=", country.id),
                    "|",
                    ("code", "=", addr.get("state")),
                    ("name", "=", addr.get("state")),
                ],
                limit=1,
            )
            if state:
                vals["state_id"] = state.id

    def _import_single_customer(self, wc):
        self.ensure_one()
        Partner = self.env["res.partner"]
        woo_id = wc.get("id")
        billing = wc.get("billing") or {}
        email = wc.get("email") or billing.get("email")
        first = wc.get("first_name") or billing.get("first_name") or ""
        last = wc.get("last_name") or billing.get("last_name") or ""
        name = (
            ("%s %s" % (first, last)).strip()
            or billing.get("company")
            or email
            or (_("Woo Customer %s") % woo_id)
        )

        partner = Partner.search([("woo_customer_id", "=", woo_id)], limit=1)
        if not partner and email:
            partner = Partner.search(
                [("email", "=", email), ("woo_customer_id", "in", (False, 0))],
                limit=1,
            )

        vals = {
            "name": name,
            "email": email,
            "woo_customer_id": woo_id,
            "woo_instance_id": self.id,
            "customer_rank": 1,
        }
        self._fill_partner_address(vals, billing)

        role = wc.get("role")
        if role:
            category = self._get_or_create_partner_category(role)
            vals["category_id"] = [(4, category.id)]

        if partner:
            partner.write(vals)
        else:
            partner = Partner.create(vals)

        self._apply_meta_data(partner, "customer", wc.get("meta_data"))
        return partner

    # ------------------------------------------------------------------
    # ORDERS
    # ------------------------------------------------------------------
    def import_orders(self):
        self.ensure_one()
        count = 0
        params = {"orderby": "date", "order": "desc"}
        if self.import_only_completed_orders:
            params["status"] = "completed"
        for wo in self._wc_iter("orders", params=params, per_page=50):
            try:
                with self.env.cr.savepoint():
                    created = self._import_single_order(wo)
                if created:
                    count += 1
            except Exception as e:
                self._woo_log(
                    "import_order", "error",
                    _("Failed to import order %s") % wo.get("id"),
                    message=str(e), woo_ref=wo.get("id"),
                )
        self.last_sync_orders = fields.Datetime.now()
        self._woo_log(
            "import_order", "info", _("Imported %s new order(s)") % count
        )
        if count:
            self.env["bus.bus"]._sendone(
                "sale.order.woo_sync",
                "new_orders",
                {"count": count, "instance": self.name},
            )
        return count

    def _import_one_order(self, woo_id):
        self.ensure_one()
        wo = self._wc_get("orders/%s" % woo_id)
        if wo:
            return self._import_single_order(wo)
        return False

    def _import_single_order(self, wo):
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        woo_order_id = str(wo.get("id") or "")
        if not woo_order_id:
            return False

        existing = SaleOrder.search([("woo_order_id", "=", woo_order_id)], limit=1)

        header_vals = {
            "woo_order_id": woo_order_id,
            "woo_instance_id": self.id,
            "woo_order_number": wo.get("number"),
            "woo_status": wo.get("status"),
            "woo_fulfillment_status": self._map_fulfillment(wo.get("status")),
            "woo_date_completed": self._parse_woo_datetime(
                wo.get("date_completed_gmt")
            ),
            "origin": "WooCommerce #%s" % (wo.get("number") or woo_order_id),
        }
        tag_ids = self._get_order_tags(wo)
        if tag_ids:
            header_vals["woo_order_tag_ids"] = [(6, 0, tag_ids)]

        if existing:
            existing.write(header_vals)
            self._apply_meta_data(existing, "order", wo.get("meta_data"))
            self._maybe_confirm_order(existing, wo)
            return False

        partner = self._get_order_partner(wo)
        shipping_partner = self._get_order_shipping_partner(wo, partner)

        create_vals = dict(header_vals)
        create_vals["partner_id"] = partner.id
        if shipping_partner:
            create_vals["partner_shipping_id"] = shipping_partner.id
        date_order = self._parse_woo_datetime(wo.get("date_created_gmt"))
        if date_order:
            create_vals["date_order"] = date_order

        order = SaleOrder.create(create_vals)
        self._build_order_lines(order, wo)
        self._apply_meta_data(order, "order", wo.get("meta_data"))
        self._maybe_confirm_order(order, wo)
        return True

    def _maybe_confirm_order(self, order, wo):
        if not self.confirm_imported_orders:
            return
        if order.state in ("sale", "cancel"):
            return
        if wo.get("status") in ("processing", "completed"):
            try:
                order.action_confirm()
            except Exception as e:
                self._woo_log(
                    "import_order", "warning",
                    _("Could not confirm order %s") % order.name,
                    message=str(e), woo_ref=wo.get("id"),
                )

    def _get_order_tags(self, wo):
        Tag = self.env["digitalnatie.woo.order.tag"]
        raw = []
        for m in wo.get("meta_data") or []:
            if m.get("key") in ("order_tags", "_order_tags", "_wc_order_tags"):
                value = m.get("value")
                if isinstance(value, (list, tuple)):
                    raw += [str(v) for v in value]
                elif value:
                    raw += [t.strip() for t in str(value).split(",")]
        tag_ids = []
        for tag_name in raw:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            tag = Tag.search([("name", "=", tag_name)], limit=1) or Tag.create(
                {"name": tag_name}
            )
            tag_ids.append(tag.id)
        return tag_ids

    def _get_order_partner(self, wo):
        Partner = self.env["res.partner"]
        customer_id = wo.get("customer_id")
        if customer_id:
            partner = Partner.search(
                [("woo_customer_id", "=", customer_id)], limit=1
            )
            if partner:
                return partner
            try:
                wc = self._wc_get("customers/%s" % customer_id)
                if wc:
                    return self._import_single_customer(wc)
            except Exception:
                pass
        return self._upsert_partner_from_billing(wo.get("billing") or {})

    def _upsert_partner_from_billing(self, billing):
        Partner = self.env["res.partner"]
        email = billing.get("email")
        first = billing.get("first_name") or ""
        last = billing.get("last_name") or ""
        name = (
            ("%s %s" % (first, last)).strip()
            or billing.get("company")
            or email
            or _("Woo Customer")
        )
        partner = False
        if email:
            partner = Partner.search([("email", "=", email)], limit=1)
        vals = {"name": name, "email": email}
        self._fill_partner_address(vals, billing)
        if partner:
            partner.write({k: v for k, v in vals.items() if v})
            return partner
        return Partner.create(vals)

    def _get_order_shipping_partner(self, wo, parent):
        shipping = wo.get("shipping") or {}
        if not shipping or not (shipping.get("address_1") or shipping.get("city")):
            return False
        Partner = self.env["res.partner"]
        name = (
            ("%s %s" % (
                shipping.get("first_name") or "",
                shipping.get("last_name") or "",
            )).strip()
            or shipping.get("company")
            or ("%s (Shipping)" % parent.name)
        )
        vals = {"name": name, "type": "delivery", "parent_id": parent.id}
        self._fill_partner_address(vals, shipping)
        existing = Partner.search(
            [("parent_id", "=", parent.id), ("type", "=", "delivery")], limit=1
        )
        if existing:
            existing.write(vals)
            return existing
        return Partner.create(vals)

    def _get_or_create_product_for_line(self, li):
        Product = self.env["product.product"]
        variation_id = li.get("variation_id")
        product_id = li.get("product_id")
        sku = li.get("sku")
        product = False
        if variation_id:
            product = Product.search(
                [("woo_variation_id", "=", variation_id)], limit=1
            )
        if not product and sku:
            product = Product.search([("default_code", "=", sku)], limit=1)
        if not product and product_id:
            tmpl = self.env["product.template"].search(
                [("woo_product_id", "=", product_id)], limit=1
            )
            if tmpl:
                product = tmpl.product_variant_id
        if product:
            return product
        vals = {
            "name": li.get("name") or _("Woo Product"),
            "type": "consu",
            "is_storable": False,
            "sale_ok": True,
            "purchase_ok": False,
            "list_price": self._to_float(li.get("price")),
        }
        if sku:
            vals["default_code"] = sku
        if product_id:
            vals["woo_product_id"] = product_id
            vals["woo_instance_id"] = self.id
        return Product.create(vals)

    def _build_order_lines(self, order, wo):
        SOL = self.env["sale.order.line"]
        no_tax = [(5, 0, 0)]

        for li in wo.get("line_items") or []:
            product = self._get_or_create_product_for_line(li)
            qty = self._to_float(li.get("quantity")) or 1.0
            subtotal = self._to_float(li.get("subtotal"))
            total = self._to_float(li.get("total"))
            if not subtotal:
                subtotal = total
            price_unit = subtotal / qty if qty else subtotal
            discount = 0.0
            if subtotal and total < subtotal:
                discount = (subtotal - total) / subtotal * 100.0
            line = SOL.create(
                {
                    "order_id": order.id,
                    "product_id": product.id,
                    "product_uom_qty": qty,
                }
            )
            line.write(
                {
                    "name": li.get("name") or product.display_name,
                    "price_unit": price_unit,
                    "discount": discount,
                    "tax_id": no_tax,
                    "woo_line_id": str(li.get("id") or ""),
                    "woo_line_type": "line_item",
                }
            )
            self._apply_meta_data(line, "order", li.get("meta_data"))

        for sh in wo.get("shipping_lines") or []:
            amount = self._to_float(sh.get("total"))
            if amount:
                self._create_charge_line(
                    order, "delivery", "shipping",
                    sh.get("method_title") or _("Delivery"), amount, sh.get("id"),
                )

        for fee in wo.get("fee_lines") or []:
            amount = self._to_float(fee.get("total"))
            if amount:
                self._create_charge_line(
                    order, "fee", "fee",
                    fee.get("name") or _("Fee"), amount, fee.get("id"),
                )

        tax_total = self._to_float(wo.get("total_tax"))
        if tax_total:
            self._create_charge_line(
                order, "tax", "tax", _("Taxes"), tax_total, False
            )

    def _create_charge_line(self, order, prod_key, line_type, label, amount, woo_id):
        product = self._get_woo_service_product(prod_key)
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product.id,
                "product_uom_qty": 1.0,
            }
        )
        line.write(
            {
                "name": label,
                "price_unit": amount,
                "discount": 0.0,
                "tax_id": [(5, 0, 0)],
                "woo_line_id": woo_id and str(woo_id) or False,
                "woo_line_type": line_type,
            }
        )
        return line

    # ------------------------------------------------------------------
    # INVENTORY / PRICE / FULFILLMENT (import side)
    # ------------------------------------------------------------------
    def _find_template(self, wp):
        """Locate the Odoo product for a WooCommerce product and keep the link.

        When a product is matched by SKU it may not yet carry the WooCommerce
        identifiers. We backfill them so that later exports (inventory, price,
        ...) can find the product again.
        """
        Tmpl = self.env["product.template"]
        woo_id = wp.get("id")
        tmpl = Tmpl.search([("woo_product_id", "=", woo_id)], limit=1)
        if not tmpl and wp.get("sku"):
            tmpl = Tmpl.search([("default_code", "=", wp.get("sku"))], limit=1)
        if tmpl:
            link_vals = {}
            if woo_id and tmpl.woo_product_id != woo_id:
                link_vals["woo_product_id"] = woo_id
            if tmpl.woo_instance_id.id != self.id:
                link_vals["woo_instance_id"] = self.id
            if link_vals:
                tmpl.write(link_vals)
        return tmpl

    def _find_variant(self, wv):
        """Locate the Odoo variant for a WooCommerce variation, keeping the link."""
        Product = self.env["product.product"]
        woo_var_id = wv.get("id")
        variant = Product.search([("woo_variation_id", "=", woo_var_id)], limit=1)
        if not variant and wv.get("sku"):
            variant = Product.search(
                [("default_code", "=", wv.get("sku"))], limit=1
            )
            if variant and woo_var_id:
                variant.woo_variation_id = woo_var_id
        return variant

    def link_products(self):
        """Backfill WooCommerce identifiers on matching Odoo products.

        This only writes ``woo_product_id`` / ``woo_instance_id`` (and
        ``woo_variation_id`` for variants) by matching on SKU. It never touches
        stock, price or any other data, so it is safe to run at any time to
        prepare products for Odoo -> WooCommerce export.
        """
        self.ensure_one()
        linked = 0
        for wp in self._wc_iter("products"):
            try:
                with self.env.cr.savepoint():
                    if self._find_template(wp):
                        linked += 1
                    if (wp.get("type") or "simple") == "variable":
                        for wv in self._wc_iter(
                            "products/%s/variations" % wp.get("id")
                        ):
                            self._find_variant(wv)
            except Exception as e:
                self._woo_log(
                    "other", "error",
                    _("Failed to link product %s") % wp.get("id"),
                    message=str(e), woo_ref=wp.get("id"),
                )
        self._woo_log(
            "other", "info",
            _("Linked %s product(s) to WooCommerce") % linked,
        )
        return linked

    def import_inventory(self):
        """Manual recovery: pull stock from WooCommerce into Odoo.

        This OVERWRITES Odoo on-hand quantities. It is not part of the regular
        or scheduled sync (which is export-only); use it only for the initial
        import or to recover Odoo stock from WooCommerce.
        """
        self.ensure_one()
        count = 0
        for wp in self._wc_iter("products"):
            try:
                with self.env.cr.savepoint():
                    if (wp.get("type") or "simple") == "variable":
                        self._find_template(wp)
                        for wv in self._wc_iter(
                            "products/%s/variations" % wp.get("id")
                        ):
                            variant = self._find_variant(wv)
                            if (
                                variant
                                and wv.get("manage_stock")
                                and wv.get("stock_quantity") is not None
                            ):
                                self._set_product_stock(
                                    variant, wv.get("stock_quantity")
                                )
                                count += 1
                        continue
                    if not wp.get("manage_stock") or wp.get("stock_quantity") is None:
                        continue
                    tmpl = self._find_template(wp)
                    if tmpl:
                        self._set_product_stock(
                            tmpl.product_variant_id, wp.get("stock_quantity")
                        )
                        count += 1
            except Exception as e:
                self._woo_log(
                    "import_stock", "error",
                    _("Failed to import stock for product %s") % wp.get("id"),
                    message=str(e), woo_ref=wp.get("id"),
                )
        self.last_sync_stock = fields.Datetime.now()
        self._woo_log(
            "import_stock", "info", _("Updated stock for %s product(s)") % count
        )
        return count

    def import_prices(self):
        """Manual recovery: pull prices from WooCommerce into Odoo.

        This OVERWRITES Odoo sales prices. It is not part of the regular or
        scheduled sync (which is export-only); use it only for the initial
        import or to recover Odoo prices from WooCommerce.
        """
        self.ensure_one()
        count = 0
        for wp in self._wc_iter("products"):
            try:
                with self.env.cr.savepoint():
                    tmpl = self._find_template(wp)
                    if not tmpl:
                        continue
                    price = wp.get("regular_price") or wp.get("price")
                    if price not in (None, "", False):
                        tmpl.list_price = self._to_float(price)
                        count += 1
            except Exception as e:
                self._woo_log(
                    "import_price", "error",
                    _("Failed to import price for product %s") % wp.get("id"),
                    message=str(e), woo_ref=wp.get("id"),
                )
        self.last_sync_prices = fields.Datetime.now()
        self._woo_log(
            "import_price", "info", _("Updated price for %s product(s)") % count
        )
        return count

    def import_fulfillment(self):
        self.ensure_one()
        count = 0
        SaleOrder = self.env["sale.order"]
        for wo in self._wc_iter("orders", per_page=100):
            try:
                with self.env.cr.savepoint():
                    order = SaleOrder.search(
                        [("woo_order_id", "=", str(wo.get("id")))], limit=1
                    )
                    if not order:
                        continue
                    order.write(
                        {
                            "woo_status": wo.get("status"),
                            "woo_fulfillment_status": self._map_fulfillment(
                                wo.get("status")
                            ),
                            "woo_date_completed": self._parse_woo_datetime(
                                wo.get("date_completed_gmt")
                            ),
                        }
                    )
                    count += 1
            except Exception as e:
                self._woo_log(
                    "import_order", "error",
                    _("Failed to import fulfillment for order %s") % wo.get("id"),
                    message=str(e), woo_ref=wo.get("id"),
                )
        self._woo_log(
            "import_order", "info",
            _("Updated fulfillment status for %s order(s)") % count,
        )
        return count
