# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ITAsset(models.Model):
    """
    Modelo abstracto base para todos los activos de TI.
    Define los campos comunes y la lógica de auditoría de incidentes.
    """
    _name = 'it.asset'
    _description = 'Activo de TI (Base)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre', required=True, tracking=True)
    description = fields.Text(string='Descripción')

    type = fields.Selection(
        selection=[
            ('user', 'Usuario')
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

    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        tracking=True,
        help="Usuario responsable del activo."
    )

    # --- LÓGICA DE INCIDENTES ---

    def _log_changes_as_incident(self, operation, changes_info=None):
        Incident = self.env['it.incident']
        for asset in self:
            title = ""
            description = ""
            severity = 'info'
            
            # ... (la lógica para title, description y severity no cambia)
            if operation == 'create':
                title = _("Nuevo Activo Creado: %s", asset.display_name)
                description = _("Se ha creado un nuevo activo de TI:\n- **Nombre:** %s\n- **Tipo:** %s\n- **Responsable:** %s",asset.name, asset.type, asset.responsible_id.name or 'N/A')
                severity = 'low'
            elif operation == 'write' and changes_info:
                title = _("Activo Actualizado: %s", asset.display_name)
                description = _("Se han detectado los siguientes cambios en el activo '%s':\n\n%s", asset.name, changes_info)
                severity = 'medium'
            elif operation == 'unlink':
                title = _("Activo Eliminado: %s", asset.display_name)
                description = _("El activo de TI '%s' (ID: %s) ha sido eliminado del sistema.", asset.display_name, asset.id)
                severity = 'high'

            if title:
                # ✅ CORRECCIÓN: Ahora poblamos los dos campos del Many2oneReference.
                incident_vals = {
                    'title': title,
                    'description': description,
                    'severity': severity,
                }
                if operation != 'unlink':
                    incident_vals['asset_model'] = asset._name
                    incident_vals['asset_ref_id'] = asset.id
                
                Incident.create(incident_vals)

    @api.model_create_multi
    def create(self, vals_list):
        assets = super().create(vals_list)
        for asset in assets:
            asset._log_changes_as_incident('create')
        return assets

    def write(self, vals):
        changes_info = []
        if vals:
            for asset in self:
                tracked_fields = {
                    'name': 'Nombre',
                    'status': 'Estado',
                    'responsible_id': 'Responsable'
                }
                for field_name, field_label in tracked_fields.items():
                    if field_name in vals:
                        old_value = asset[field_name].display_name if hasattr(asset[field_name], 'display_name') else asset[field_name]
                        new_value = vals[field_name]
                        if isinstance(self._fields[field_name], fields.Many2one) and new_value:
                            new_value = self.env[self._fields[field_name].comodel_name].browse(new_value).display_name
                        
                        changes_info.append(f"- **{field_label}:** de '{old_value or 'N/A'}' a '{new_value or 'N/A'}'")
        
        res = super().write(vals)

        if changes_info:
            self._log_changes_as_incident('write', "\n".join(changes_info))
        
        return res

    def unlink(self):
        self._log_changes_as_incident('unlink')
        return super().unlink()