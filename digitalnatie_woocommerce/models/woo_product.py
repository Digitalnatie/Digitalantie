from odoo import _, fields, models
from odoo.exceptions import UserError


class ProductCategory(models.Model):
    _inherit = "product.category"

    woo_category_id = fields.Integer(
        string="WooCommerce Category ID",
        copy=False,
        index=True,
    )


class ProductTag(models.Model):
    _inherit = "product.tag"

    woo_tag_id = fields.Integer(
        string="WooCommerce Tag ID",
        copy=False,
        index=True,
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    woo_product_id = fields.Integer(
        string="WooCommerce Product ID",
        copy=False,
        index=True,
        help="ID of the product in WooCommerce.",
    )
    woo_instance_id = fields.Many2one(
        "digitalnatie.woo.instance",
        string="WooCommerce Instance",
        copy=False,
        index=True,
    )
    woo_published = fields.Boolean(
        string="Published on WooCommerce",
        copy=False,
        help="Whether the product is published (visible) on the WooCommerce store.",
    )
    woo_image_url = fields.Char(
        string="WooCommerce Image URL",
        copy=False,
        help="Source URL of the main product image, used when exporting images.",
    )
    woo_meta_data = fields.Json(
        string="WooCommerce Meta Data",
        copy=False,
    )
    woo_last_export = fields.Datetime(string="Last WooCommerce Export", copy=False)
    woo_last_import = fields.Datetime(string="Last WooCommerce Import", copy=False)

    def _woo_get_instance(self):
        self.ensure_one()
        instance = self.woo_instance_id
        if not instance:
            instance = self.env["digitalnatie.woo.instance"].search(
                [("is_active", "=", True)], limit=1
            )
        if not instance:
            raise UserError(
                _("No WooCommerce instance is configured for this product.")
            )
        return instance

    def action_woo_export(self):
        for product in self:
            instance = product._woo_get_instance()
            instance._export_one_product(product)
        return True

    def action_woo_publish(self):
        for product in self:
            instance = product._woo_get_instance()
            instance._set_product_published(product, True)
        return True

    def action_woo_unpublish(self):
        for product in self:
            instance = product._woo_get_instance()
            instance._set_product_published(product, False)
        return True


class ProductProduct(models.Model):
    _inherit = "product.product"

    woo_variation_id = fields.Integer(
        string="WooCommerce Variation ID",
        copy=False,
        index=True,
        help="ID of the product variation in WooCommerce.",
    )
    woo_meta_data = fields.Json(
        string="WooCommerce Meta Data",
        copy=False,
    )
