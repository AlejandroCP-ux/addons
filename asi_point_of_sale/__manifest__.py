{
    'name': 'ASI Reportes Punto de Venta',
    'version': '2.4',
    'summary': 'Extiende los reportes de ventas del POS con información de costos y ganancias',
    'description': """
        Este módulo agrega tres columnas adicionales a los reportes de detalles de ventas del POS:
        - COSTE: El costo del producto
        - COSTE x CANTIDAD: La multiplicación del costo por la cantidad
        - GANANCIA: El precio por la cantidad menos el costo por la cantidad
        
        También añade un asistente para generar reportes de ventas por períodos específicos.
    """,
    'author': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/report_saledetails.xml',
        'wizard/pos_sales_report_wizard_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
