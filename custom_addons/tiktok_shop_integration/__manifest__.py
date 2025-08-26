{
    'name': 'TikTok Shop Integration',
    'version': '16.0.1.0.0',
    'category': 'Tools',
    'summary': 'Integrate Odoo with TikTok Shop APIs',
    'description': """
        TikTok Shop Integration for Odoo 16

        Utilities to authorize and test TikTok Shop APIs.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/tiktok_api_tester_wizard_view.xml',
        'views/gchat_config_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 