{
    'name': 'Stock Expiry Alert',
    'version': '19.0.1.0.0',
    'summary': 'Proactive alerts before stock lots and serials reach their expiration date.',
    'sequence': 1,
    'description': "Scans lots and serial numbers with an expiration date and alerts key personnel before stock expires unnoticed.",
    'category': 'Inventory/Inventory',
    'author': 'Mindsynth Technologies',
    'maintainer': 'Mehedi Hasan Rakib',
    'website': 'https://mindsynthtech.com',
    'license': 'OPL-1',
    'depends': [
        'stock',
        'product_expiry',
        'mail',
    ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',

        'data/mail_template.xml',
        'data/ir_cron_data.xml',

        'views/config_views.xml',
        'views/expiring_lots_views.xml',
        'views/menus.xml',
    ],


    'images': [
        'static/description/banner.png',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'price': 0.00,
    'currency': 'USD',
}