# -*- coding: utf-8 -*-

{
    'name': 'Base User Roles Extended',
    'author': 'Javier',
    'version': '16.0',
    'category': 'Human Resources',
    'sequence': 85,
    'summary': """Employee Contract Roles""",
    'maintainer': 'ASI',
    'website': '',
    'description': """
        This module implement a custom access control depending of employee contracted roles.""",
    "license": "AGPL-3",
    'support': '',
    'depends': ['hr_contract','base_user_role'],
    'data': [
                'views/role_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
