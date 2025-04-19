# -*- coding: utf-8 -*-

{
    'name': 'Odoo Local IA Integration',
    'version': '16.0.1.0.0',
    'license': 'AGPL-3',
    'summary': 'Odoo ChatGPT Integration',
    'description': 'Odoo-IA connection',
    'author': 'Javier',
    'company': 'InTechual Solutions',
    'website': 'https://www.asisurl.cu',
    'depends': ['base', 'base_setup', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/localai_model_data.xml',
        'data/mail_channel_data.xml',
        'data/user_partner_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {'python': ['openai']},
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
