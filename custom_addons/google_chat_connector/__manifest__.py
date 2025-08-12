# -*- coding: utf-8 -*-
{
    'name': 'Google Chat Connector for Odoo',
    'summary': 'Send Odoo notifications to Google Chat instead of email. Avoid email spam!',
    'version': '1.0.0',
    'category': 'Tools',
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'license': 'OPL-1',
    'depends': ['base', 'mail', 'sale_management', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/test_message_wizard_view.xml',
        'views/google_config_views.xml',
        'views/google_log_views.xml',
        'views/google_chat_mapping_view.xml',

        # ...
    ],
    'assets': {
        'web.assets_backend': [
            'google_chat_connector/static/src/**/*',
        ],
    },
    'installable': True,
    'application': True,
}
