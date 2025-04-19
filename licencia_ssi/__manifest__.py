# __manifest__.py
{
    "name": "Generador de Licencia SSI",
    "version": "0.1",
    "summary": "Generates a license code based on a seed and a secret key.",
    "author": "Your Name",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/license_generator_view.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False
}