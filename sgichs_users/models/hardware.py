# -*- coding: utf-8 -*-
from odoo import models, fields

class Hardware(models.Model):
    # COMENTARIO: Esta herencia ahora es segura gracias a la dependencia
    # declarada en el __manifest__.py.
    _inherit = 'it.asset.hardware'

    # COMENTARIO: Estamos SOBREESCRIBIENDO el campo 'responsible_id' que
    # venía del modelo 'it.asset' en el core.
    # Originalmente era un Many2one a 'res.users'.
    # Ahora lo convertimos en un Many2one a nuestro nuevo modelo 'it.user'.
    responsible_id = fields.Many2one(
        'it.user', # Apunta a nuestro nuevo modelo.
        string='Usuario Responsable',
        tracking=True,
        # Añadimos un dominio para que solo se puedan seleccionar usuarios de TI activos.
        domain="[('status', '=', 'active')]"
    )
