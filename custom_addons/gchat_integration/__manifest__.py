{
    'name': 'Google Chat Integration',
    'version': '16.0.1.0.0',
    'category': 'Project',
    'summary': 'Integrate Odoo Projects with Google Chat Spaces',
    'description': """
        Google Chat Integration for Odoo 16
        
        Features:
        - Project ↔ Google Chat Space mapping
        - Task ↔ Thread synchronization
        - Outbound notifications (Odoo → Chat)
        - Inbound webhook support (Chat → Odoo)
        - Pub/Sub listener for real-time updates
        - Multi-company support
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'project',
        'mail',
        'web',
    ],
    'data': [
        'security/gchat_security.xml',
        'security/ir.model.access.csv',
        'views/gchat_menus.xml',
        'views/gchat_config_views.xml',
        'views/gchat_space_views.xml',
        'views/gchat_thread_views.xml',
        'views/gchat_subscription_views.xml',
        'views/gchat_member_views.xml',
        'views/gchat_event_log_views.xml',
        'views/project_inherit_views.xml',
        'wizard/gchat_space_wizard_views.xml',
        'data/ir_cron.xml',
        'data/params.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gchat_integration/static/src/js/gchat_utils.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 