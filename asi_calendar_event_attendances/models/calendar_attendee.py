# -*- coding: utf-8 -*-
# Parte de Odoo. Ver archivo LICENSE para detalles completos de licencia.

from odoo import api, fields, models, _
from datetime import date

class Attendee(models.Model):
    _inherit = 'calendar.attendee'

    has_participated = fields.Boolean(
        string='Ha asistido', 
        default=False,
        help='Indica si el asistente ha marcado su asistencia en el evento')
    
    can_mark_participation = fields.Boolean(
        string='Puede marcar asistencia', 
        compute='_compute_can_mark_participation',
        help='Indica si el asistente puede marcar su asistencia en este momento')
    
    # Añadir un campo para mostrar la fecha del evento de forma legible
    event_date = fields.Char(
        string='Fecha del evento',
        compute='_compute_event_date',
        store=True,
        help='Fecha del evento en formato legible')

    @api.depends('event_id.start')
    def _compute_event_date(self):
        """Calcula una representación legible de la fecha del evento"""
        for attendee in self:
            if attendee.event_id and attendee.event_id.start:
                # Formato: "15/04/2023"
                attendee.event_date = attendee.event_id.start.strftime("%d/%m/%Y")
            else:
                attendee.event_date = False

    @api.depends('event_id.is_in_current_month_until_today', 'partner_id', 'has_participated')
    def _compute_can_mark_participation(self):
        """Determina si el asistente puede marcar su asistencia"""
        current_partner = self.env.user.partner_id
        for attendee in self:
            # Puede marcar asistencia si:
            # 1. El evento ocurrió desde el día 1 del mes actual hasta hoy
            # 2. Es el asistente actual
            # 3. Aún no ha marcado su asistencia
            attendee.can_mark_participation = (
                attendee.event_id.is_in_current_month_until_today and 
                attendee.partner_id == current_partner and
                not attendee.has_participated
            )

    def mark_participation(self):
        """Marca la asistencia del asistente en el evento"""
        self.ensure_one()
        if self.can_mark_participation:
            self.has_participated = True
            self.event_id.message_post(
                body=_("%s ha marcado su asistencia en el evento") % self.partner_id.name,
                subtype_xmlid="mail.mt_note"
            )
            return True
        return False

    def get_participation_info(self):
        """Devuelve información de asistencia para la API"""
        self.ensure_one()
        return {
            'id': self.id,
            'event_id': self.event_id.id,
            'partner_id': self.partner_id.id,
            'has_participated': self.has_participated,
            'can_mark_participation': self.can_mark_participation,
        }

    # Modificar el método para recargar la vista después de marcar asistencias
    @api.model
    def mark_participation_multi(self, ids):
        """Marca la asistencia de múltiples asistentes a la vez"""
        attendees = self.browse(ids)
        marked_count = 0
        
        for attendee in attendees:
            if attendee.can_mark_participation:
                attendee.has_participated = True
                attendee.event_id.message_post(
                    body=_("%s ha marcado su asistencia en el evento") % attendee.partner_id.name,
                    subtype_xmlid="mail.mt_note"
                )
                marked_count += 1
        
        # Devolver una acción que recargue la vista actual
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'menu_id': self.env.context.get('menu_id'),
                'action': self.env.context.get('action'),
                'id': self.env.context.get('id'),
            }
        }

