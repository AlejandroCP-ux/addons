{
    'name': 'Drag & Drop PDF Upload',
    'version': '1.0',
    'summary': 'Permite subir archivos PDF arrastrándolos al wizard de firma',
    'category': 'Tools',
    'author': 'Javier',
    'depends': ['asi_pdf_signature'],
    'data': [
        'views/firma_documento_views.xml',        
    ],
    'assets': {
        'web.assets_backend': [
            'drag_drop_pdf_upload/static/src/js/drag_drop.js',
            'drag_drop_pdf_upload/static/src/css/drag_drop.css',
        ],
    },
    'installable': True,
    'application': False,
}
