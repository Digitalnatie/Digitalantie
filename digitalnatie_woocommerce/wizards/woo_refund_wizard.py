from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DigitalnatieWooRefundWizard(models.TransientModel):
    _name = "digitalnatie.woo.refund.wizard"
    _description = "WooCommerce Refund Wizard"

    order_id = fields.Many2one(
        "sale.order", string="Order", required=True, ondelete="cascade"
    )
    order_total = fields.Monetary(
        related="order_id.amount_total", string="Order Total", readonly=True
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id", readonly=True
    )
    refund_type = fields.Selection(
        [("full", "Full Refund"), ("partial", "Partial Refund")],
        string="Refund Type",
        default="partial",
        required=True,
    )
    amount = fields.Monetary(string="Refund Amount", currency_field="currency_id")
    reason = fields.Char(string="Reason")
    restock_items = fields.Boolean(
        string="Process via Payment Gateway",
        default=True,
        help="When enabled, WooCommerce attempts an automatic refund through the "
        "original payment gateway (api_refund).",
    )

    @api.onchange("refund_type")
    def _onchange_refund_type(self):
        if self.refund_type == "full":
            self.amount = self.order_id.amount_total

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        if not order.woo_instance_id or not order.woo_order_id:
            raise UserError(
                _("Order %s is not linked to a WooCommerce instance.") % order.name
            )
        amount = self.amount
        if self.refund_type == "full":
            amount = order.amount_total
        order.woo_instance_id._push_refund(
            order, amount, self.reason, self.restock_items
        )
        return {"type": "ir.actions.act_window_close"}
