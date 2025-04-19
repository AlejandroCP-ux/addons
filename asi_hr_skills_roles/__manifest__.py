{
    'name': 'Custom HR Skill Type',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Custom module to extend HR Skill Type',
    'depends': ['hr_skills', 'base'],
    'license': 'AGPL-3',    
    'data': [
        'views/hr_skills_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}