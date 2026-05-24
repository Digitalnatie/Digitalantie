from odoo import fields, models


class DigitalnatieWooMetaMapping(models.Model):
    _name = "digitalnatie.woo.meta.mapping"
    _description = "WooCommerce Custom/Meta Field Mapping"
    _order = "woo_object, woo_meta_key"

    instance_id = fields.Many2one(
        "digitalnatie.woo.instance",
        string="Instance",
        required=True,
        ondelete="cascade",
        index=True,
    )
    woo_object = fields.Selection(
        [
            ("product", "Product"),
            ("variant", "Product Variant"),
            ("customer", "Customer"),
            ("order", "Order"),
        ],
        string="WooCommerce Object",
        required=True,
    )
    woo_meta_key = fields.Char(
        string="WooCommerce Meta Key",
        required=True,
        help="Key of the entry inside the WooCommerce 'meta_data' list.",
    )
    odoo_field_name = fields.Char(
        string="Odoo Field",
        required=True,
        help="Technical name of the field on the matching Odoo model "
        "(product.template, product.product, res.partner or sale.order).",
    )
    direction = fields.Selection(
        [
            ("import", "Import only"),
            ("export", "Export only"),
            ("both", "Bidirectional"),
        ],
        string="Direction",
        default="both",
        required=True,
    )
    active = fields.Boolean(default=True)
