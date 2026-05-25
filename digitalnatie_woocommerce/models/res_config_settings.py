# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Global WooCommerce Connector settings.

    Per-store credentials (URL, consumer key, secret) live on the
    ``digitalnatie.woo.instance`` records so that multiple stores can be
    connected. These settings are the global defaults applied to every
    instance.
    """
    _inherit = 'res.config.settings'

    woo_request_timeout = fields.Integer(
        string='Request Timeout (seconds)',
        config_parameter='digitalnatie_woocommerce.request_timeout',
        default=90,
        help='Maximum time (in seconds) to wait for a WooCommerce REST API '
             'response before aborting the call.',
    )
    woo_page_size = fields.Integer(
        string='Pagination Size',
        config_parameter='digitalnatie_woocommerce.page_size',
        default=100,
        help='Number of records fetched per WooCommerce API page during '
             'imports. WooCommerce caps this at 100.',
    )
    woo_log_retention_days = fields.Integer(
        string='Log Retention (days)',
        config_parameter='digitalnatie_woocommerce.log_retention_days',
        default=30,
        help='Sync log entries older than this number of days are deleted '
             'by the daily cleanup cron. Set to 0 to keep logs forever.',
    )
    woo_log_level = fields.Selection(
        [('info', 'Info (all operations)'),
         ('warning', 'Warning (warnings and errors only)'),
         ('error', 'Error (errors only)')],
        string='Log Level',
        config_parameter='digitalnatie_woocommerce.log_level',
        default='info',
        help='Minimum severity recorded in the WooCommerce sync log.',
    )
