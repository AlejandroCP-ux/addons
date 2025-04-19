# -*- coding: utf-8 -*-
# Parte de Odoo. Ver archivo LICENSE para detalles completos de licencia.

{
    'name': 'Participación en Eventos de Calendario',
    'version': '2.5',
    'category': 'Productivity/Calendar',
    'summary': 'Permite a los asistentes marcar su participación en eventos',
    'description': """
Participación en Eventos de Calendario
======================================
Este módulo extiende la funcionalidad del calendario para permitir:
- Que los asistentes marquen su participación durante eventos en curso
- Que el organizador vea quiénes participaron en el evento
- Que los asistentes vean si participaron o no en eventos pasados
    """,
    'depends': ['calendar'],
    'data': [
        'security/ir.model.access.csv',
        'views/calendar_event_views.xml',
        'views/calendar_attendee_views.xml',
        'views/calendar_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'asi_calendar_event_attendances/static/src/js/calendar_controller.js',
            'asi_calendar_event_attendances/static/src/js/calendar_model.js',
            'asi_calendar_event_attendances/static/src/js/calendar_renderer.js',
            'asi_calendar_event_attendances/static/src/scss/calendar_participation.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

