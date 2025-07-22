# -*- coding: utf-8 -*-
{
    'name': "SGICH Core",
    'summary': """
        Módulo base para la Gestión de Infraestructura y Cambios de TI.
        Proporciona los modelos centrales para la gestión de activos,
        incidentes y tareas programadas.""",
    'author': "Tu Nombre",
    'website': "https://www.tuweb.com",
    'category': 'IT/Infrastructure',
    'version': '16.0.1.0.0',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/it_asset_views.xml',
        'views/it_asset_backlog_views.xml',
        'views/incident_views.xml',
        'views/scheduled_task_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}