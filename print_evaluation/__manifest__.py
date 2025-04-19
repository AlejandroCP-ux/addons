{
    'name': 'Informe de Evaluación',
    'version': '16.0.1',
  'summary': 'Genera informes de evaluación de desempeño',
    'description': 'Módulo para generar informes de evaluación de desempeño filtrados por período y departamento.',
    'author': 'Alejandro Cespedes Perez',
    'depends': ['performance_evaluation'],
    'website': "www.asisurl.cu",
    'data': [
        'security/ir.model.access.csv',
        'views/report_wizard_views.xml',
        'views/performance_evaluation_views.xml',
        'report/performance_report.xml',
        'report/performance_report_list.xml',
    ],
    'installable': True,
    'application': False,
}
