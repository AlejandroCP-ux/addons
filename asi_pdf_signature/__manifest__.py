{
    'name': 'ASI Firma Digital de Documentos',
    'version': '2.0',  # Cambiar de 1.9 a 2.0
    'summary': 'Módulo para firmar documentos PDF digitalmente',
    'description': """
        Este módulo permite:
        - Agregar certificado de firma digital e imagen de firma a los usuarios
        - Subir, firmar digitalmente y descargar documentos PDF
        - Almacenar contraseña del certificado de forma cifrada
    """,
    'category': 'Herramientas',
    'author': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'depends': ['base', 'web'],
    'data': [
        'security/security.xml',        
        'data/signature_tags.xml',
        'views/res_users_views.xml',
        'wizards/firma_documento_views.xml',
        'wizards/seleccionar_archivos_views.xml',
        'views/firma_digital_menu.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'asi_pdf_signature/static/src/js/firma_digital.js',
            'asi_pdf_signature/static/src/css/firma_digital.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'technical_name': 'asi_pdf_signature',
}
