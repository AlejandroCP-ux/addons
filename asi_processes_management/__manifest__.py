{
    'name': 'Gestión de Procesos Internos',
    'version': '1.0',
    'summary': 'Gestión estructurada de procesos y actividades recurrentes',
    'category': 'Operations',
    'author': 'Javier Escobar',
    'website': 'https://www.asisurl.cu',
    'depends': ['base', 'calendar', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/x_process_views.xml'
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
}
