{
    'name': 'Digitalnatie WooCommerce Connector',
    'version': '18.0.2.2.0',
    'author': 'Digitalnatie',
    'website': 'https://digitalnatie.be',
    'category': 'Sales',
    'summary': 'Bi-directional WooCommerce <-> Odoo connector (Digitalnatie)',
    'description': """
Digitalnatie WooCommerce Connector
==================================
Synchronise WooCommerce client shops with Odoo:

* Import products (variants, descriptions, tags, categories, price, inventory, images)
* Import customers and orders (tags, discounts, delivery, fees, taxes)
* Import/export custom (meta) fields for products, variants, customers and orders
* Export/update products, inventory, prices and publication state to WooCommerce
* Export fulfillment status and handle full/partial refunds
* Instant updates through WooCommerce webhooks
* Scheduled bi-directional synchronisation
""",
    'depends': ['base', 'product', 'sale_management', 'stock', 'web', 'bus'],
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
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
