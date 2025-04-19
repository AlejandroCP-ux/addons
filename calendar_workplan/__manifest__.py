# -*- coding: utf-8 -*-
{
    'name': "Work Plan Management",

    'summary': """
        Implementacion de la Instruccion No 1 del Plan de Trabajo en Cuba""",

    'description': """
        Long description of module's purpose
    """,

    'author': "ASI S.R.L.",
    'website': "https://www.desoft.cu",
    "contact": 'comercial@lt.desoft.cu',

    # Categories can be used to filter modules in modules listing
    'category': 'Productivity',
    'version': '16.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'calendar', 'mail', 'hr', 'base_automation', 'gamification'],

    # always loaded
    'data': [
        'security/calendar_workplan_groups.xml',
        'security/ir.model.access.csv',
        'data/base_automation_data.xml',
        'data/ir_cron_actions.xml',
        'data/calendar_workplan_section_data.xml',
        'reports/workplan_report.xml',
        'reports/individual_plan_report.xml',
        'reports/annual_plan_report.xml',
        'views/calendar_event_views.xml',
        'views/res_company_views.xml',
        'views/calendar_workplan_section_views.xml',
        'views/calendar_workplan_plan_views.xml',
        'views/gamification_challenge_views.xml',
        'views/calendar_workplan_menus.xml',  
        ],
        
    # only loaded in demonstration mode
     'demo': [
         'data/res_users_demo.xml',
         'data/hr_employee_demo.xml',
         'data/gamification_challenge_demo.xml',
         'data/calendar_workplan_plan_demo.xml',
         'data/calendar_event_demo.xml',
     ],
}
