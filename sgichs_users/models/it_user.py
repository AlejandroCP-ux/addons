# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ITUser(models.Model):
    _name = 'it.user'
    _description = 'Usuario Autorizado de TI'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    user_id = fields.Many2one(
        'res.users',
        string='Usuario del Sistema',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(related='user_id.name', readonly=True, store=True)
    status = fields.Selection(
        selection=[
            ('active', 'Activo'),
            ('revoked', 'Revocado')
        ],
        string='Estado de Autorización',
        default='active',
        tracking=True
    )
    notes = fields.Text(string='Observaciones')

    # COMENTARIO: Esta es la relación inversa. Como 'sgichs_hardware' es ahora una
    # dependencia garantizada, podemos definir este campo de forma segura y directa.
    # El 'inverse_name' debe coincidir con el campo en 'it.asset.hardware'.
    hardware_ids = fields.One2many(
        'it.asset.hardware',
        'responsible_id',
        string='Hardware Asignado'
    )

    _sql_constraints = [
        ('unique_user', 'UNIQUE(user_id)', 'Cada usuario del sistema solo puede tener una autorización de TI.')
    ]

    def action_revoke(self):
        """Revoca la autorización y desasigna el hardware."""
        self.ensure_one()
        # Al revocar, desasignamos al usuario de cualquier hardware que tuviera.
        self.hardware_ids.write({'responsible_id': False})
        self.status = 'revoked'
        self.message_post(body="Autorización revocada y hardware desasignado.")