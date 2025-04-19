# -*- coding: utf-8 -*-
{
    'name': "Accounting Extension",

    'summary': 'Extension in Accounting, Accounting Extension, Enable Accounting Features, Enable Canceling Entries by Defaults, Add Accounts Company Domain for Contact/Product/Product Category, Multiple Company - Invoice Accounts/Journal Company Validation',
    
    'description' : """
        * enable accounting features
    """,

    "author": "Openinside",
    "license": "OPL-1",
    'website': "https://www.open-inside.com",
    "price" : 0,
    "currency": 'USD',
    'category': 'Accounting',
    'version': '16.0.1.1.6',
    'images':[
        'static/description/cover.png'
        ], 

    # any module necessary for this one to work correctly
    'depends': ['account','payment'],
    'excludes' : ['account_accountant'],

    # always loaded
    'data': [
        'security/group.xml',
        'view/action.xml',       
        'view/menu.xml',
        'view/res_config_settings_views.xml'
        
    ],    
    'odoo-apps' : True,
    'auto_install': False,
}