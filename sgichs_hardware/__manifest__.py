# -*- coding: utf-8 -*-
{
    'name': "SGICH Hardware Management",
    'summary': """
        Extiende el core de SGICH para añadir una gestión detallada
        de activos de hardware y sus componentes.""",
    'author': "Tu Nombre",
    'website': "https://www.tuweb.com",
    'category': 'IT/Infrastructure',
    'version': '16.0.1.0.0',
    # COMENTARIO: Dependencia explícita del módulo core.
    'depends': ['sgichs_core2'],
    'data': [
        'security/ir.model.access.csv',
        'views/component_subtype_views.xml',
        'views/component_views.xml',
        'views/hardware_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}