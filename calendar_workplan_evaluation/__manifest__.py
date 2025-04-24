# -*- coding: utf-8 -*-
{
    'name': 'Workplan Evaluation with IA',
    'version': '16.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Evaluación del cumplimiento de los planes de trabajo con IA local',
    'depends': ['calendar_workplan', 'asi_ia'],
    'data': [
        'views/calendar_workplan_plan_view_inherit_eval.xml',
        'security/ir.model.access.csv',
        'views/evaluation_view.xml',
        'report/evaluation_report_template.xml',
        'report/evaluation_report_action.xml',
    ],
    'installable': True,
    'auto_install': False,
}
