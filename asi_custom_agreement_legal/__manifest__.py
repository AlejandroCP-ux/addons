{
    'name': 'ASI Custom Agreement',
    'version': '1.0',
    'summary': 'Custom module to modify Agreement report',
    'description': 'This module inherits from agreement_legal and modifies the Agreement report by removing the Parties section.',
    'category': 'Custom',
    'author': 'Javier',
    'depends': ['agreement_legal'],
    'license': 'AGPL-3',
    'data': [
        'views/agreement_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}