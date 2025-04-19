# -*- coding: utf-8 -*-

{
    'name': 'Employee Contract Roles',
    'author': 'Javier',
    'version': '16.0',
    'category': 'Human Resources',
    'sequence': 85,
    'summary': """Employee Contract Roles""",
    'maintainer': 'ASI',
    'website': '',
    'description': """
        This module adds a list of roles and levels required to fullfill the contract.Also links contract´s dates negin/end with uer Roles begin/end""",
    'license': 'AGPL-3',
    'support': '',
    'depends': ['hr_contract','base_user_role'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_contract_views.xml',        
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
