{
    'name': 'Custom Partner Form',
    'version': '1.0',
    'summary': 'Custom module to add account holder, currency, and bank address to partner form',
    'description': 'This module adds fields for account holder, currency, and bank address to the partner form.',
    'category': 'Custom',
    'author': 'Javier',
    'depends': ['base'],
    'license': 'AGPL-3',
    'data': [
        'views/partner_view.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}