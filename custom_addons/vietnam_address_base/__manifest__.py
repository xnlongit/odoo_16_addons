# -*- coding: utf-8 -*-
{
    'name': 'Vietnam Address Base',
    'summary': """The Vietnam Address Base module is an extension for the Odoo system designed to provide a comprehensive database of addresses in Vietnam.""",
    'author': 'magenest',
    'license': 'LGPL-3',
    'category': 'Extra Tools',
    'version': '18.0.1.0',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'data/res_country_state_data.xml',
        'data/ir_cron_data.xml',
        'data/res.country.ward.csv',
        'views/res_country_ward_views.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/menus.xml'
    ],
    'images': ['static/description/thumbnail.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
}
