# -*- coding: utf-8 -*-
{
    'name': 'Personalización de Flota',
    'version': '1.0',
    'category': 'Human Resources/Fleet',
    'summary': 'Personalización del módulo de flota con funcionalidades adicionales',
    'description': """
Personalización del Módulo de Flota
===================================
Este módulo añade las siguientes funcionalidades al módulo de flota:
- Tipos de actividad
- Hojas de ruta
- Índices de consumo
- Registro de combustible
- Campos adicionales para vehículos
- Mantenimientos programados y no programados
- Planes de consumo de combustible
- Pruebas de consumo de combustible
- Modelo de combustible habilitado y kilómetros recorridos
- Control de vencimiento de FICAV
- Control de kilómetros disponibles para mantenimiento
- Alertas automáticas para mantenimiento y FICAV
- Sistema de notificaciones automáticas
- Informes de nivel de actividad por equipos
- Informes de índice de consumo
- Informes de análisis de consumo de combustible
- Informe de kilómetros totales recorridos
- Informe Plan vs Real para comparación de consumo
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'depends': ['fleet', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/fleet_notification_cron.xml',
        'wizards/fleet_ficav_renewal_wizard_views.xml',
        'report/fleet_route_sheet_report.xml',
        'report/fleet_consumption_test_report.xml',
        'report/fleet_route_sheet_control_wizard.xml',
        'views/fleet_activity_type_views.xml',
        'views/fleet_route_sheet_views.xml',
        'views/fleet_consumption_index_views.xml',
        'views/fleet_fuel_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_maintenance_views.xml',
        'views/fleet_consumption_plan_views.xml',
        'views/fleet_consumption_test_views.xml',
        'views/fleet_fuel_record_views.xml',
        'views/fleet_activity_report_views.xml',
        'views/fleet_consumption_index_report_views.xml',
        'views/fleet_consumption_analysis_report_views.xml',
        'views/fleet_kilometers_report_views.xml',
        'views/fleet_activity_report_view_views.xml',
        'views/fleet_ficav_alert_views.xml',
        'views/fleet_plan_vs_real_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
