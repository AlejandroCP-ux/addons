{
    "name": "ASI Alfresco PDF Signature",
    "version": "16.0.1.0.0",
    "summary": "Módulo para firmar archivos PDF desde integración con Alfresco",
    "category": "Tools",
    "author": "tv asi",
    "license": "AGPL-3",
    "depends": [
        "asi_alfresco_integration",
        "asi_pdf_signature"
    ],
    'external_dependencies': {
    'python': ['requests','endesive', 'pypdf', 'Pillow', 'pyOpenSSL']
    },
    "data": [
        "security/ir.model.access.csv",
        "wizards/alfresco_firma_wizard_views.xml",
        "data/alfresco_actions.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}
