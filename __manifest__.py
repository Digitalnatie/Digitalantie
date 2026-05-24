# -*- coding: utf-8 -*-
{
    'name': 'WooCommerce Connector',
    'version': '18.0.3.0.0',
    'category': 'Sales/Sales',
    'summary': 'Bi-directional WooCommerce <-> Odoo connector with multi-instance, webhooks and meta-field mapping',
    'description': """
WooCommerce Connector for Odoo 18 Community
===========================================
Synchronise one or several WooCommerce stores with Odoo:

* Import products, variants, categories, images, taxes, customers and orders
* Export products, prices, stock, categories, images and order status updates
* Stock and prices: Odoo is the single source of truth (scheduled push only,
  manual recovery import available)
* Instant updates through signed WooCommerce webhooks
* Configurable bi-directional sync per object (product, customer, order,
  inventory, price, fulfillment)
* Custom field (meta_data) mapping per object type
* Multi-instance: connect as many WooCommerce stores as you need
* Built-in sync logs with operation, level and WooCommerce reference
* Cron jobs for unattended synchronisation (disabled by default; activate
  per your needs)
* Refund wizard for partial / full WooCommerce refunds from Odoo
* No external SaaS, no telemetry, no activation key
""",
    'author': 'Digitalnatie',
    'maintainer': 'Digitalnatie',
    'website': 'https://digitalnatie.be',
    'support': 'support@digitalnatie.be',
    'license': 'OPL-1',
    'price': 199.00,
    'currency': 'EUR',
    'depends': [
        'base',
        'product',
        'sale_management',
        'stock',
        'web',
        'bus',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/woo_instance_views.xml',
        'views/woo_log_views.xml',
        'views/woo_meta_views.xml',
        'views/woo_product_views.xml',
        'views/woo_partner_views.xml',
        'views/woo_sale_order_views.xml',
        'views/woo_refund_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/woo_menu.xml',
        'data/woo_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'digitalnatie_woocommerce/static/src/js/woo_sync_notification.js',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
