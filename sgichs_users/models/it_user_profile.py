# RUTA: sgichs_users/models/it_user_profile.py (CÓDIGO ACTUALIZADO)

# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ITUserProfile(models.Model):
    _name = 'it.user.profile'
    _description = 'Perfil de Usuario de TI'
    # AÑADIMOS EL MIXIN DE MAIL PARA TENER CHATTER
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre del Perfil',
        required=True,
        tracking=True,
        help='Ej: Desarrollador, Trabajador, Administrador'
    )
    description = fields.Text(
        string='Descripción',
        help='Detalles sobre las características y permisos del perfil'
    )
    user_ids = fields.Many2many(
        'it.user',
        inverse_name='profile_ids',
        string='Usuarios Asociados',
        tracking=True,
        help='Usuarios que tienen este perfil asignado'
    )

    _sql_constraints = [
        ('unique_profile_name', 'UNIQUE(name)', 'El nombre del perfil debe ser único')
    ]

    # --- NUEVA LÓGICA DE INCIDENTES PARA ESTE MODELO ---

    def _log_profile_changes_as_incident(self, operation, changes_info=None):
        """Crea incidentes específicamente para cambios en perfiles."""
        Incident = self.env['it.incident']
        for profile in self:
            title = ""
            description = ""
            severity = 'info'

            # La lógica para obtener título, desc, etc. no cambia.
            if operation == 'create':
                title = _("Nuevo Perfil Creado: %s", profile.name)
                description = _("Se ha creado un nuevo perfil de usuario: %s", profile.name)
                severity = 'low'
            elif operation == 'write' and changes_info:
                title = _("Perfil Actualizado: %s", profile.name)
                description = _("Se han detectado cambios en el perfil '%s':\n\n%s", profile.name, changes_info)
                severity = 'medium'
            elif operation == 'unlink':
                title = _("Perfil Eliminado: %s", profile.name)
                description = _("El perfil de usuario '%s' (ID: %s) ha sido eliminado.", profile.name, profile.id)
                severity = 'high'

            if title:
                # ✅ CORRECCIÓN: Usamos los nuevos campos de almacenamiento para crear el incidente.
                incident_vals = {
                    'title': title,
                    'description': description,
                    'severity': severity,
                }
                # Los perfiles no son activos, pero los referenciamos para tener trazabilidad.
                if operation != 'unlink':
                    incident_vals['asset_model'] = profile._name
                    incident_vals['asset_id'] = profile.id

                Incident.create(incident_vals)

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)
        for profile in profiles:
            profile._log_profile_changes_as_incident('create')
        return profiles

    def write(self, vals):
        changes_info = []
        if vals:
            for profile in self:
                if 'user_ids' in vals:
                    old_users = ", ".join(profile.user_ids.mapped('name')) or 'N/A'
                    # El tracking de Many2many es más complejo, lo simplificamos a "ha cambiado"
                    changes_info.append(f"- **Usuarios Asociados:** han cambiado.")
                if 'description' in vals:
                    changes_info.append(f"- **Descripción:** ha sido modificada.")

        res = super().write(vals)

        if changes_info:
            self._log_profile_changes_as_incident('write', "\n".join(changes_info))
        return res

    def unlink(self):
        self._log_profile_changes_as_incident('unlink')
        return super().unlink()