# RUTA: sgichs_users/models/it_user.py (CÓDIGO ACTUALIZADO)

# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ITUser(models.Model):
    _name = 'it.user'
    _description = 'Usuario Autorizado de TI'
    # La herencia de 'it.asset' le da automáticamente la lógica de incidentes
    _inherit = ['it.asset'] 

    # Campo 'type' requerido por it.asset. Lo forzamos a 'user'.
    type = fields.Selection(
        selection_add=[('user', 'Usuario')],
        ondelete={'user': 'cascade'},
        default='user'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Usuario del Sistema',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    # El campo 'name' ya viene de it.asset, lo relacionamos con el usuario de Odoo
    name = fields.Char(related='user_id.name', readonly=True, store=True, required=False)

    # El campo 'status' ya existe en 'it.asset', lo adaptamos.
    # Aquí puedes agregar más estados si lo necesitas en el futuro.
    status = fields.Selection(
        selection_add=[
            ('revoked', 'Revocado')
        ],
        tracking=True
    )
    
    notes = fields.Text(string='Observaciones')

    hardware_ids = fields.One2many(
        'it.asset.hardware',
        'responsible_id',
        string='Hardware Asignado'
    )
    
    profile_ids = fields.Many2many(
        'it.user.profile',
        relation='it_user_profile_rel',
        column1='user_id',
        column2='profile_id',
        string='Perfiles Asignados',
        tracking=True,
        help='Todos los perfiles funcionales asignados al usuario'
    )

    _sql_constraints = [
        ('unique_user', 'UNIQUE(user_id)', 'Cada usuario del sistema solo puede tener una autorización de TI.')
    ]

    def action_revoke(self):
        """Revoca la autorización y desasigna el hardware."""
        self.ensure_one()
        self.hardware_ids.write({'responsible_id': False})
        # Usamos el estado 'retired' de it.asset que es más genérico
        self.status = 'retired' 
        self.message_post(body=_("Autorización revocada y hardware desasignado."))

    def write(self, vals):
        """
        Sobrescribimos write para añadir el seguimiento de campos específicos
        de este modelo, como los perfiles.
        """
        changes_info = []
        if 'profile_ids' in vals:
            for user in self:
                # Obtenemos los nombres de los perfiles antes del cambio
                old_profiles = ", ".join(user.profile_ids.mapped('name')) or 'N/A'
                # Obtenemos los nuevos IDs desde los comandos (6, 0, [IDs])
                new_profile_ids = []
                for command in vals['profile_ids']:
                    if command[0] == 6:
                        new_profile_ids = command[2]
                        break
                new_profiles = ", ".join(self.env['it.user.profile'].browse(new_profile_ids).mapped('name')) or 'N/A'
                
                changes_info.append(f"- **Perfiles Asignados:** de '{old_profiles}' a '{new_profiles}'")

        # Llamamos al 'write' original, que ya tiene la lógica de incidentes de it.asset
        res = super().write(vals)

        # Si detectamos cambios en los perfiles, generamos un incidente adicional
        if changes_info:
            self._log_changes_as_incident('write', "\n".join(changes_info))

        return res