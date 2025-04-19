{
    'name': 'ASI Custom Role Menu Hidding',
    'version': '16.0.1.0.0',
    'category': 'Hidden',
    'author': 'Javier Escobar',
    'license': 'LGPL-3',
    'summary': 'Hide menu items based on user roles',
    'description': """
        This module allows hiding menu items based on user roles.
    """,
    'depends': ['base', 'base_user_role'],
    'data': [
        'views/res_users_role_view.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}