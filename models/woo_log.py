from datetime import timedelta

from odoo import api, fields, models


class DigitalnatieWooLog(models.Model):
    _name = "digitalnatie.woo.log"
    _description = "WooCommerce Sync Log"
    _order = "create_date desc"
    _rec_name = "summary"

    @api.model
    def cron_cleanup_logs(self):
        """Delete log entries older than the configured retention.

        Retention is read from the system parameter
        ``digitalnatie_woocommerce.log_retention_days``. A value of 0 keeps
        logs forever.
        """
        param = self.env['ir.config_parameter'].sudo().get_param(
            'digitalnatie_woocommerce.log_retention_days', '30'
        )
        try:
            days = int(param)
        except (TypeError, ValueError):
            days = 30
        if days <= 0:
            return
        cutoff = fields.Datetime.now() - timedelta(days=days)
        self.sudo().search([('create_date', '<', cutoff)]).unlink()

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
