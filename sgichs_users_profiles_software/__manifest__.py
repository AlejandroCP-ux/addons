# -*- coding: utf-8 -*-
{
    'name': "SGICH Users Profiles Management",
    'summary': """Añade la opcion de perfiles al gestor de usuarios permiteindo mejor control sobre los usuarios y sus permisos sobre otros modulos.""",
    'author': "Luis Javier Espinosa Cutie",
    'website': "https://www.tuweb.com",
    'category': 'IT/Infrastructure',
    'version': '16.0.1.0.1',
    'depends': ['sgichs_core2', 'sgichs_hardware','sgichs_software', 'sgichs_users'],
    "data": [
        "security/ir.model.access.csv",
        'wizards/add_software_from_list_wizard_views.xml',
        'wizards/remove_software_from_list_wizard_views.xml',
        'views/it_user_profile_views.xml',
        'views/software_views.xml',
        
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}