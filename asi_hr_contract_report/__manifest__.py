# -*- coding: utf-8 -*-

{
    'name': 'Employee Contract Report',
    'author': 'rolandoperezrebollo',
    'version': '16.0',
    'category': 'Human Resources',
    'summary': """Employee Contract Report""",
    'maintainer': 'desoft.cu',
    'description': """
        This module adds a report template for contract.""",
    'license': 'OPL-1',
    'depends': ['hr_contract', 'asi_hr_contract_roles' ],
    'data': [
        'report/ir_actions_report_templates.xml', 
        'report/ir_actions_report.xml',       
    ],
    'installable': True    
}
