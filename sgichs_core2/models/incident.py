# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class Incident(models.Model):
    _name = 'it.incident'
    _description = 'Incidente de TI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'detection_date desc'

    title = fields.Char(string='Título', required=True, tracking=True)
    description = fields.Text(string='Descripción Detallada')
    severity = fields.Selection(
        selection=[
            ('info', 'Informativo'), ('low', 'Baja'),
            ('medium', 'Media'), ('high', 'Alta')
        ],
        string='Severidad', default='medium', tracking=True
    )
    status = fields.Selection(
        [('new', 'Nuevo'), ('in_progress', 'En Progreso'),
         ('resolved', 'Resuelto'), ('closed', 'Cerrado')],
        default='new', string="Estado", tracking=True
    )
    detection_date = fields.Datetime(
        string='Fecha de Detección', default=fields.Datetime.now, readonly=True
    )

    # --- INICIO DE LA SOLUCIÓN DEFINITIVA ---
    # Reemplazamos toda la lógica anterior con un único campo Many2oneReference.
    # Este campo es dinámico y Odoo lo maneja internamente de forma robusta.
    # El modelo se determina por el campo 'asset_model' y el ID por este campo.
    asset_ref_id = fields.Many2oneReference(
        string='Activo Relacionado',
        model_field='asset_model',
        help="Activo de TI relacionado con este incidente."
    )
    # Este campo auxiliar le dice al campo de arriba qué modelo buscar.
    asset_model = fields.Char(
        string='Modelo del Activo',
        readonly=True,
        index=True
    )
    # --- FIN DE LA SOLUCIÓN DEFINITIVA ---

    def _send_user_notification(self):
        # ... (esta función no cambia)
        for incident in self:
            severity_to_type = {
                'high': 'danger', 'medium': 'warning',
                'low': 'info', 'info': 'info'
            }
            notification_type = severity_to_type.get(incident.severity, 'info')
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': incident.title,
                    'message': _('Se ha generado un nuevo incidente de TI.'),
                    'type': notification_type,
                    'sticky': False,
                }
            }
            self.env['bus.bus']._sendone(
                self.env.user.partner_id,
                'mail.message.user.notification',
                message
            )

    @api.model_create_multi
    def create(self, vals_list):
        incidents = super().create(vals_list)
        incidents._send_user_notification()
        return incidents