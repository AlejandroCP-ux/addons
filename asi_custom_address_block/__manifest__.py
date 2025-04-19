{
    'name': 'Custom Address Block',
    'version': '1.0',
    'summary': 'Custom module to personalize address block in Odoo reports',
    'description': 'This module allows customization of the address block in Odoo reports.',
    'category': 'Custom',
    'author': 'Javier',
    'depends': ['base'],
    "license": "AGPL-3",
    'data': [
        'views/report_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}