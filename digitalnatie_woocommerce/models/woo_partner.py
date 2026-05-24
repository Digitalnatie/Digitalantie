from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    woo_customer_id = fields.Integer(
        string="WooCommerce Customer ID",
        copy=False,
        index=True,
        help="ID of the customer in WooCommerce.",
    )
    woo_instance_id = fields.Many2one(
        "digitalnatie.woo.instance",
        string="WooCommerce Instance",
        copy=False,
        index=True,
    )
    woo_meta_data = fields.Json(
        string="WooCommerce Meta Data",
        copy=False,
    )
