# __manifest__.py

{
    'name': 'Custom Contact QR',
    'version': '1.0',
    'author': 'Javier Escobar',
    'category': 'Extra Tools',
    'depends': ['base'],
    'data': ['views/contact_view.xml'],
    'external_dependencies': {
        'python': ['qrcode'],
    },
    'images': ['static/description/banner.gif'],
}
