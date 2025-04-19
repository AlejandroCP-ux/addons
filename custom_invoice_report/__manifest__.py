{
    'name': 'Custom Sale Order/Invoice Report',
    'version': '1.0',
    'summary': 'Custom Sale Order/Invoice Report',
    'author': 'rolandoperezrebollo',
    'depends': ['base', 'web', 'sale', 'account', 'product', 'asi_custom_sale'],
    'data': [
        'views/res_partner_views.xml',
        'report/custom_report_inherit.xml',
    ],
}
