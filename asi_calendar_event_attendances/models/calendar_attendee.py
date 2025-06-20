# -*- coding: utf-8 -*-
# Parte de Odoo. Ver archivo LICENSE para detalles completos de licencia.

from odoo import api, fields, models, _
from datetime import date
from odoo import SUPERUSER_ID
import logging
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

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
    event_date = fields.Date(
        string='Fecha del evento',
        compute='_compute_event_date',
        store=True,
        index=True,  # Indexar para mejorar rendimiento de búsquedas
        help='Fecha del evento')
        
    # Campos para facilitar el filtrado por mes
    event_month = fields.Integer(
        string='Mes del evento',
        compute='_compute_event_date',
        store=True,
        index=True,
        help='Mes del evento (1-12)')
        
    event_year = fields.Integer(
        string='Año del evento',
        compute='_compute_event_date',
        store=True,
        index=True,
        help='Año del evento')

    @api.depends('event_id.start')
    def _compute_event_date(self):
        """Calcula la fecha, mes y año del evento"""
        for attendee in self:
            if attendee.event_id and attendee.event_id.start:
                event_date = attendee.event_id.start.date()
                attendee.event_date = event_date
                attendee.event_month = event_date.month
                attendee.event_year = event_date.year
                _logger.info(f"Asistente {attendee.id} - Evento {attendee.event_id.name}: fecha={event_date}, mes={event_date.month}, año={event_date.year}")
            else:
                attendee.event_date = False
                attendee.event_month = False
                attendee.event_year = False

    @api.depends('event_id.is_in_current_month_until_today', 'partner_id', 'has_participated')
    def _compute_can_mark_participation(self):
        """Determina si el asistente puede marcar su asistencia"""
        current_partner = self.env.user.partner_id
        for attendee in self:
            # Puede marcar asistencia si:
            # 1. El evento ocurrió desde el día 1 del mes actual hasta hoy
            # 2. Es el asistente actual
            # 3. Aún no ha marcado su asistencia
            # 4. O es administrador/superusuario
            is_admin = self.env.user.has_group("base.group_system") or self.env.user.id == SUPERUSER_ID
        
            attendee.can_mark_participation = (
                ((attendee.event_id.is_in_current_month_until_today or attendee.event_id.is_ongoing) and 
                attendee.partner_id == current_partner and
                not attendee.has_participated) or is_admin
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

    def admin_mark_participation(self):
        """Marca la asistencia del asistente en el evento (para administradores)"""
        self.ensure_one()
        if self.env.user.has_group("base.group_system") or self.env.user.id == SUPERUSER_ID:
            self.has_participated = True
            self.event_id.message_post(
                body=_("%s ha sido marcado como asistente por %s") % (self.partner_id.name, self.env.user.name),
                subtype_xmlid="mail.mt_note"
            )
            return True
        return False

    # Modificar el método para recargar la vista después de marcar asistencias
    @api.model
    def mark_participation_multi(self, ids):
        """Marca la asistencia de múltiples asistentes a la vez"""
        attendees = self.browse(ids)
        marked_count = 0
        is_admin = self.env.user.has_group("base.group_system") or self.env.user.id == SUPERUSER_ID
    
        for attendee in attendees:
            if attendee.can_mark_participation or is_admin:
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
        
    # Método para obtener el mes y año actual
    @api.model
    def _get_current_month_year(self):
        today = fields.Date.today()
        return today.month, today.year
        
    # Método para obtener el mes y año anterior
    @api.model
    def _get_last_month_year(self):
        today = fields.Date.today()
        last_month_date = today - relativedelta(months=1)
        return last_month_date.month, last_month_date.year
        
    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Extiende el método de búsqueda para aplicar filtros personalizados"""
        # Ya no necesitamos este método, ya que estamos usando dominios directos
        return super(Attendee, self).search(args, offset, limit, order, count)
