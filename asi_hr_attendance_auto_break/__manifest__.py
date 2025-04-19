# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'ASI HR Attendance Lunch Break',
    'version': '1.8',
    'category': 'Human Resources/Attendances',
    'summary': 'Automaticamente gestiona los registros de asistencia durante la hora del almuerzo',
    'description': """
HR Attendance Lunch Break
=========================
This module automatically manages attendance records during lunch time:
- Creates a check-out at 12:00 PM for employees with open attendance records
- Creates a new check-in at 12:30 PM for those employees

Gestión de Asistencias en Hora de Almuerzo
==========================================
Este módulo gestiona automáticamente los registros de asistencia durante la hora del almuerzo:
- Crea un registro de salida a las 12:00 PM para empleados con registros de asistencia abiertos
- Crea un nuevo registro de entrada a las 12:30 PM para esos empleados
    """,
    'depends': ['hr_attendance'],
    'data': [
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'i18n_languages': ['es', 'en'],
}
