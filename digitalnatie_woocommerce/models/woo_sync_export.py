import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DigitalnatieWooInstanceExport(models.Model):
    _inherit = "digitalnatie.woo.instance"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_variant_qty(self, variant):
        location = self._get_stock_location()
        if location:
            return variant.with_context(location=location.id).qty_available
        return variant.qty_available

    def _ensure_woo_category(self, categ):
        """Return the WooCommerce category id for an Odoo category, creating it."""
        if categ.woo_category_id:
            return categ.woo_category_id
        found = self._wc_get("products/categories", params={"search": categ.name})
        for fc in found or []:
            if (fc.get("name") or "").strip().lower() == (
                categ.name or ""
            ).strip().lower():
                categ.woo_category_id = fc["id"]
                return fc["id"]
        result = self._wc_post("products/categories", {"name": categ.name})
        if result.get("id"):
            categ.woo_category_id = result["id"]
            return result["id"]
        return False

    def _ensure_woo_tag(self, tag):
        if tag.woo_tag_id:
            return tag.woo_tag_id
        found = self._wc_get("products/tags", params={"search": tag.name})
        for ft in found or []:
            if (ft.get("name") or "").strip().lower() == (
                tag.name or ""
            ).strip().lower():
                tag.woo_tag_id = ft["id"]
                return ft["id"]
        result = self._wc_post("products/tags", {"name": tag.name})
        if result.get("id"):
            tag.woo_tag_id = result["id"]
            return result["id"]
        return False

    # ------------------------------------------------------------------
    # PRODUCTS (export)
    # ------------------------------------------------------------------
    def export_products(self):
        self.ensure_one()
        products = self.env["product.template"].search(
            [("woo_instance_id", "=", self.id)]
        )
        count = 0
        for product in products:
            try:
                with self.env.cr.savepoint():
                    self._export_one_product(product)
                count += 1
            except Exception as e:
                self._woo_log(
                    "export_product", "error",
                    _("Failed to export product %s") % product.display_name,
                    message=str(e), res_model="product.template", res_id=product.id,
                )
        self._woo_log(
            "export_product", "info", _("Exported %s product(s)") % count
        )
        return count

    def _build_product_attributes(self, product):
        attributes = []
        for line in product.attribute_line_ids:
            attributes.append(
                {
                    "name": line.attribute_id.name,
                    "visible": True,
                    "variation": True,
                    "options": line.value_ids.mapped("name"),
                }
            )
        return attributes

    def _build_product_payload(self, product):
        payload = {
            "name": product.name,
            "regular_price": str(product.list_price or 0.0),
            "description": product.description_sale or "",
            "weight": str(product.weight or 0.0),
            "status": "publish" if product.woo_published else "draft",
        }
        if product.default_code:
            payload["sku"] = product.default_code

        if len(product.product_variant_ids) > 1:
            payload["type"] = "variable"
            payload["attributes"] = self._build_product_attributes(product)
        else:
            payload["type"] = "simple"
            if product.is_storable:
                payload["manage_stock"] = True
                payload["stock_quantity"] = int(
                    self._get_variant_qty(product.product_variant_id)
                )

        if product.categ_id:
            woo_cat = self._ensure_woo_category(product.categ_id)
            if woo_cat:
                payload["categories"] = [{"id": woo_cat}]

        tag_payload = []
        for tag in product.product_tag_ids:
            woo_tag = self._ensure_woo_tag(tag)
            if woo_tag:
                tag_payload.append({"id": woo_tag})
        if tag_payload:
            payload["tags"] = tag_payload

        if product.woo_image_url:
            payload["images"] = [{"src": product.woo_image_url}]

        meta = self._build_meta_export(product, "product")
        if meta:
            payload["meta_data"] = meta
        return payload

    def _export_one_product(self, product):
        self.ensure_one()
        payload = self._build_product_payload(product)
        if product.woo_product_id:
            self._wc_put("products/%s" % product.woo_product_id, payload)
        else:
            result = self._wc_post("products", payload)
            if result.get("id"):
                product.woo_product_id = result["id"]
        product.woo_instance_id = self.id
        product.woo_last_export = fields.Datetime.now()

        if product.woo_product_id and len(product.product_variant_ids) > 1:
            self._export_product_variants(product)

        self._woo_log(
            "export_product", "info",
            _("Exported product %s") % product.display_name,
            woo_ref=product.woo_product_id,
            res_model="product.template", res_id=product.id,
        )
        return product.woo_product_id

    def _export_product_variants(self, product):
        woo_id = product.woo_product_id
        for variant in product.product_variant_ids:
            payload = {
                "regular_price": str(variant.lst_price or 0.0),
                "attributes": [
                    {
                        "name": ptav.attribute_id.name,
                        "option": ptav.name,
                    }
                    for ptav in variant.product_template_variant_value_ids
                ],
            }
            if variant.default_code:
                payload["sku"] = variant.default_code
            if product.is_storable:
                payload["manage_stock"] = True
                payload["stock_quantity"] = int(self._get_variant_qty(variant))
            meta = self._build_meta_export(variant, "variant")
            if meta:
                payload["meta_data"] = meta
            if variant.woo_variation_id:
                self._wc_put(
                    "products/%s/variations/%s" % (woo_id, variant.woo_variation_id),
                    payload,
                )
            else:
                result = self._wc_post(
                    "products/%s/variations" % woo_id, payload
                )
                if result.get("id"):
                    variant.woo_variation_id = result["id"]

    def _set_product_published(self, product, published):
        self.ensure_one()
        if not product.woo_product_id:
            self._export_one_product(product)
        if not product.woo_product_id:
            raise UserError(
                _("Product %s could not be created in WooCommerce.")
                % product.display_name
            )
        self._wc_put(
            "products/%s" % product.woo_product_id,
            {"status": "publish" if published else "draft"},
        )
        product.woo_published = published
        self._woo_log(
            "export_product", "info",
            _("%s product %s")
            % (published and _("Published") or _("Unpublished"), product.display_name),
            woo_ref=product.woo_product_id,
            res_model="product.template", res_id=product.id,
        )

    # ------------------------------------------------------------------
    # INVENTORY / PRICE (export)
    # ------------------------------------------------------------------
    def export_inventory(self):
        self.ensure_one()
        products = self.env["product.template"].search(
            [
                ("woo_instance_id", "=", self.id),
                ("woo_product_id", "!=", False),
                ("is_storable", "=", True),
            ]
        )
        count = 0
        for product in products:
            try:
                with self.env.cr.savepoint():
                    if len(product.product_variant_ids) > 1:
                        for variant in product.product_variant_ids.filtered(
                            "woo_variation_id"
                        ):
                            self._wc_put(
                                "products/%s/variations/%s"
                                % (product.woo_product_id, variant.woo_variation_id),
                                {
                                    "manage_stock": True,
                                    "stock_quantity": int(
                                        self._get_variant_qty(variant)
                                    ),
                                },
                            )
                            count += 1
                    else:
                        self._wc_put(
                            "products/%s" % product.woo_product_id,
                            {
                                "manage_stock": True,
                                "stock_quantity": int(
                                    self._get_variant_qty(product.product_variant_id)
                                ),
                            },
                        )
                        count += 1
            except Exception as e:
                self._woo_log(
                    "export_stock", "error",
                    _("Failed to export stock for %s") % product.display_name,
                    message=str(e), res_model="product.template", res_id=product.id,
                )
        self.last_sync_stock = fields.Datetime.now()
        self._woo_log(
            "export_stock", "info", _("Exported stock for %s product(s)") % count
        )
        return count

    def export_prices(self):
        self.ensure_one()
        products = self.env["product.template"].search(
            [
                ("woo_instance_id", "=", self.id),
                ("woo_product_id", "!=", False),
            ]
        )
        count = 0
        for product in products:
            try:
                with self.env.cr.savepoint():
                    if len(product.product_variant_ids) > 1:
                        for variant in product.product_variant_ids.filtered(
                            "woo_variation_id"
                        ):
                            self._wc_put(
                                "products/%s/variations/%s"
                                % (product.woo_product_id, variant.woo_variation_id),
                                {"regular_price": str(variant.lst_price or 0.0)},
                            )
                            count += 1
                    else:
                        self._wc_put(
                            "products/%s" % product.woo_product_id,
                            {"regular_price": str(product.list_price or 0.0)},
                        )
                        count += 1
            except Exception as e:
                self._woo_log(
                    "export_price", "error",
                    _("Failed to export price for %s") % product.display_name,
                    message=str(e), res_model="product.template", res_id=product.id,
                )
        self.last_sync_prices = fields.Datetime.now()
        self._woo_log(
            "export_price", "info", _("Exported price for %s product(s)") % count
        )
        return count

    # ------------------------------------------------------------------
    # ORDER STATUS (export)
    # ------------------------------------------------------------------
    def _odoo_order_is_fulfilled(self, order):
        pickings = order.picking_ids
        if pickings:
            return any(p.state == "done" for p in pickings) and all(
                p.state in ("done", "cancel") for p in pickings
            )
        return order.state == "sale"

    def _export_one_order_status(self, order):
        self.ensure_one()
        if not order.woo_order_id:
            raise UserError(
                _("Order %s is not linked to WooCommerce.") % order.name
            )
        status = "cancelled" if order.state == "cancel" else "completed"
        payload = {"status": status}
        meta = self._build_meta_export(order, "order")
        if meta:
            payload["meta_data"] = meta
        self._wc_put("orders/%s" % order.woo_order_id, payload)
        order.write(
            {
                "woo_status": status,
                "woo_fulfillment_status": self._map_fulfillment(status),
            }
        )
        self._woo_log(
            "export_order", "info",
            _("Order %s set to '%s' in WooCommerce") % (order.name, status),
            woo_ref=order.woo_order_id,
            res_model="sale.order", res_id=order.id,
        )

    def export_order_statuses(self):
        self.ensure_one()
        orders = self.env["sale.order"].search(
            [
                ("woo_instance_id", "=", self.id),
                ("woo_order_id", "!=", False),
                ("state", "=", "sale"),
            ]
        )
        count = 0
        for order in orders:
            try:
                if order.woo_status == "completed":
                    continue
                if not self._odoo_order_is_fulfilled(order):
                    continue
                with self.env.cr.savepoint():
                    self._export_one_order_status(order)
                count += 1
            except Exception as e:
                self._woo_log(
                    "export_order", "error",
                    _("Failed to export status for order %s") % order.name,
                    message=str(e), res_model="sale.order", res_id=order.id,
                )
        self._woo_log(
            "export_order", "info",
            _("Exported fulfillment status for %s order(s)") % count,
        )
        return count

    # ------------------------------------------------------------------
    # REFUNDS (export)
    # ------------------------------------------------------------------
    def _push_refund(self, order, amount, reason, restock=True):
        self.ensure_one()
        if not order.woo_order_id:
            raise UserError(
                _("Order %s is not linked to WooCommerce.") % order.name
            )
        if amount <= 0:
            raise UserError(_("The refund amount must be greater than zero."))
        payload = {
            "amount": str(amount),
            "reason": reason or "",
            "api_refund": bool(restock),
        }
        result = self._wc_post(
            "orders/%s/refunds" % order.woo_order_id, payload
        )
        is_full = abs(amount - (order.amount_total or 0.0)) < 0.01
        order.write(
            {
                "woo_status": "refunded" if is_full else order.woo_status,
                "woo_fulfillment_status": "refunded"
                if is_full
                else order.woo_fulfillment_status,
            }
        )
        self._woo_log(
            "refund", "info",
            _("%s refund of %s on order %s")
            % (is_full and _("Full") or _("Partial"), amount, order.name),
            woo_ref=order.woo_order_id,
            res_model="sale.order", res_id=order.id,
        )
        return result
