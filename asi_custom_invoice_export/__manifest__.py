{
    'name': 'Custom Invoice Export',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Export selected invoices to plain text file',
    'author': 'Javier',
    'website': '',
    'depends': ['account'],
    'license': 'AGPL-3',
    'data': [
    	'security/ir.model.access.csv',
        'wizard/invoice_export_wizard_view.xml',
        'data/custom_invoice_export_actions.xml',        
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}