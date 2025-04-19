# -*- coding: utf-8 -*-
{
    'name': "Perfomance Evaluation",

    'summary': """
         Extend functionality for performance Evaluation""",

    'description': """
        This will be used for the Employee performance evaluation Program in the system.
        Javier. Included Default template in hr.form
    """,

    'author': "Vaibhav, Snackat",
    'website': "www.snackat.com",
    'images': ["static/description/evaluation_prog.png"],

    'category': 'Human Resources/Employees',
    'version': '16.0.1',
    'license': 'AGPL-3',
    'depends': ['hr', 'base'],
    'data': [
        'security/performance_evaluation_security.xml',
        'security/ir.model.access.csv',
        'views/performance_evaluation_view.xml',
        'views/hr_employee_views.xml',
        'data/ir_sequence_data.xml',
    ],

    'installable': True,
    'application': True,
        
}
