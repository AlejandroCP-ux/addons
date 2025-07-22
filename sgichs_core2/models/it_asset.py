# -*- coding: utf-8 -*-
from odoo import models, fields

class ITAsset(models.Model):
    """
    Modelo abstracto base para todos los activos de TI.
    Define los campos comunes que compartirán hardware, software, etc.
    """
    _name = 'it.asset'
    _description = 'Activo de TI (Base)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre', required=True, tracking=True)
    description = fields.Text(string='Descripción')

    # COMENTARIO: El campo 'type' es crucial y se usará para determinar
    # la naturaleza del activo. Los módulos extensores añadirán sus propios tipos.
    type = fields.Selection(
        selection=[
            # Esta lista será extendida por otros módulos.
        ],
        string='Tipo de Activo',
        required=True,
        tracking=True
    )

    status = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('active', 'Activo'),
            ('in_repair', 'En Reparación'),
            ('retired', 'Retirado'),
        ],
        string='Estado',
        default='draft',
        tracking=True
    )

    # COMENTARIO: Se relaciona con 'res.users' de forma predeterminada.
    # El módulo 'sgich_users' puede heredar este campo para cambiarlo a 'it.user'
    # y añadir lógica de dominios o reglas más complejas si es necesario.
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        tracking=True,
        help="Usuario responsable del activo."
    )