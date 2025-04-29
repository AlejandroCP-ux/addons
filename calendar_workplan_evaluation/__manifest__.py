# -*- coding: utf-8 -*-
{
    'name': 'Workplan Evaluation with IA',
    'version': '16.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Evaluación del cumplimiento de los planes de trabajo con IA local',
    'depends': ['calendar_workplan', 'asi_ia','asi_calendar_event_attendances'],
    'data': [
        'views/calendar_workplan_plan_view_inherit_eval.xml',
     ],
    'installable': True,
    'auto_install': False,
}
