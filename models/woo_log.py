from odoo import fields, models


class DigitalnatieWooLog(models.Model):
    _name = "digitalnatie.woo.log"
    _description = "WooCommerce Sync Log"
    _order = "create_date desc"
    _rec_name = "summary"

    instance_id = fields.Many2one(
        "digitalnatie.woo.instance",
        string="Instance",
        ondelete="cascade",
        index=True,
    )
    operation = fields.Selection(
        [
            ("import_product", "Import Product"),
            ("export_product", "Export Product"),
            ("import_customer", "Import Customer"),
            ("import_order", "Import Order"),
            ("export_order", "Export Order Status"),
            ("import_stock", "Import Inventory"),
            ("export_stock", "Export Inventory"),
            ("import_price", "Import Price"),
            ("export_price", "Export Price"),
            ("refund", "Refund"),
            ("webhook", "Webhook"),
            ("connection", "Connection"),
            ("other", "Other"),
        ],
        string="Operation",
        default="other",
        index=True,
    )
    level = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        string="Level",
        default="info",
        index=True,
    )
    summary = fields.Char(string="Summary", required=True)
    message = fields.Text(string="Details")
    woo_ref = fields.Char(string="WooCommerce Reference")
    res_model = fields.Char(string="Odoo Model")
    res_id = fields.Integer(string="Odoo Record ID")
