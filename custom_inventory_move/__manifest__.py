{
    'name': "custom_inventory_move",

    'summary': 'Muestra la cantidad restante después de cada movimiento de inventario',

    'description': """
Muestra la cantidad restante después de cada movimiento de inventario
    """,

    'author': "Alejandro Cespedes Perez",
    'website': "https://www.asisurl.cu",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['stock'],

    'data': [
        'views/stock_move_views.xml',
    ],

}

