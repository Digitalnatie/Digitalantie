from odoo import _, fields, models
from odoo.exceptions import UserError


class DigitalnatieWooOrderTag(models.Model):
    _name = "digitalnatie.woo.order.tag"
    _description = "WooCommerce Order Tag"
    _order = "name"

    name = fields.Char(string="Tag", required=True)
    color = fields.Integer(string="Color")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "Order tag names must be unique."),
    ]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    woo_order_id = fields.Char(
        string="WooCommerce Order ID",
        copy=False,
        index=True,
        help="ID of the order in WooCommerce.",
    )
    woo_instance_id = fields.Many2one(
        "digitalnatie.woo.instance",
        string="WooCommerce Instance",
        copy=False,
        index=True,
    )
    woo_order_number = fields.Char(string="WooCommerce Order Number", copy=False)
    woo_status = fields.Char(string="WooCommerce Status", copy=False)
    woo_fulfillment_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("fulfilled", "Fulfilled"),
            ("cancelled", "Cancelled"),
            ("refunded", "Refunded"),
        ],
        string="Fulfillment Status",
        copy=False,
    )
    woo_date_completed = fields.Datetime(string="WooCommerce Completed Date", copy=False)
    woo_order_tag_ids = fields.Many2many(
        "digitalnatie.woo.order.tag",
        string="WooCommerce Order Tags",
        copy=False,
    )
    woo_meta_data = fields.Json(string="WooCommerce Meta Data", copy=False)

    def action_woo_export_status(self):
        for order in self:
            if not order.woo_instance_id or not order.woo_order_id:
                raise UserError(
                    _("Order %s is not linked to a WooCommerce instance.") % order.name
                )
            order.woo_instance_id._export_one_order_status(order)
        return True

    def action_woo_open_refund(self):
        self.ensure_one()
        if not self.woo_instance_id or not self.woo_order_id:
            raise UserError(
                _("Order %s is not linked to a WooCommerce instance.") % self.name
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("WooCommerce Refund"),
            "res_model": "digitalnatie.woo.refund.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    woo_line_id = fields.Char(string="WooCommerce Line ID", copy=False, index=True)
    woo_line_type = fields.Selection(
        [
            ("line_item", "Product"),
            ("shipping", "Delivery"),
            ("fee", "Fee"),
            ("discount", "Discount"),
            ("tax", "Tax"),
        ],
        string="WooCommerce Line Type",
        copy=False,
    )
    woo_meta_data = fields.Json(string="WooCommerce Meta Data", copy=False)
