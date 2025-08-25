{
    'name': 'Módulo de Reporting SGICHS',
    'version': '1.0',
    'summary': 'Generación de reportes para el Sistema de Gestión Integral de TI',
    'description': 'Módulo para generar reportes personalizados de hardware, software, incidentes y otros componentes del sistema SGICHS.',
    'category': 'Reporting',
    'author': 'Tu Nombre',
    'website': 'https://tusitio.com',
    'depends': [
        'base', 
        'web', 
        'sgichs_core2', 
        'sgichs_hardware',
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/report_actions.xml',
        'report/hardware_technical_sheet.xml',
        'views/hardware_views.xml',
        'views/custom_report_views.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            # Puedes añadir archivos SCSS/CSS aquí si los tienes
        ],
    },
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}