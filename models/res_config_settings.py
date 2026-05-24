from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    woo_store_url = fields.Char(
        string='WooCommerce Store URL',
        config_parameter='digitalnatie_woocommerce.woo_store_url',
    )
    woo_consumer_key = fields.Char(
        string='Consumer Key',
        config_parameter='digitalnatie_woocommerce.woo_consumer_key',
    )
    woo_consumer_secret = fields.Char(
        string='Consumer Secret',
        config_parameter='digitalnatie_woocommerce.woo_consumer_secret',
    )
