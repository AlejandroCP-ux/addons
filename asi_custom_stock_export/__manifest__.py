{
    'name': 'Custom Stock Move Export',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Export selected stock moves to plain text file',
    'author': 'Javier Escobar',
    'website': 'www.asisurl.cu',
    'depends': ['account','stock'],
    'license': 'AGPL-3',
    'data': [
    	'security/ir.model.access.csv',
        'wizard/stock_move_export_wizard_view.xml',    
        'data/custom_stock_move_export_actions.xml',   
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}