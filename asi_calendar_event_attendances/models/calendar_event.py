# -*- coding: utf-8 -*-
# Parte de Odoo. Ver archivo LICENSE para detalles completos de licencia.

from datetime import datetime, timedelta, date
import calendar
from odoo import api, fields, models, _

class Meeting(models.Model):
    _inherit = 'calendar.event'

    # Campos para controlar la participación
    is_ongoing = fields.Boolean(
        string='En curso', 
        compute='_compute_is_ongoing', 
        store=True,  # Almacenar en la base de datos para búsquedas
        help='Indica si el evento está actualmente en curso')
    
    is_in_current_month_until_today = fields.Boolean(
        string='En mes actual hasta hoy', 
        compute='_compute_is_in_current_month_until_today', 
        store=True,  # Almacenar en la base de datos para búsquedas
        help='Indica si el evento ocurrió desde el día 1 del mes actual hasta hoy')
    
    participation_count = fields.Integer(
        string='Asistentes', 
        compute='_compute_participation_count',
        store=True,  # Almacenar en la base de datos para búsquedas
        help='Número de asistentes que han marcado su asistencia')
    
    participation_percentage = fields.Float(
        string='Porcentaje de asistencia', 
        compute='_compute_participation_count',
        store=True,  # Almacenar en la base de datos para búsquedas
        help='Porcentaje de asistentes que han marcado su asistencia')
    
    event_date_display = fields.Char(
        string='Fecha del evento',
        compute='_compute_event_date_display',
        store=True,
        help='Fecha del evento en formato legible')

    @api.depends('start', 'stop')
    def _compute_is_ongoing(self):
        """Determina si el evento está actualmente en curso"""
        now = fields.Datetime.today()
        for event in self:
            event.is_ongoing = event.start <= now
    
    # Modificar para incluir todos los eventos del día actual
    @api.depends('start', 'stop')
    def _compute_is_in_current_month_until_today(self):
        """Determina si el evento ocurrió desde el día 1 del mes actual hasta hoy (inclusive)"""
        today = fields.Date.today()
        first_day_of_month = date(today.year, today.month, 1)
        
        for event in self:
            # Convertir datetime a date para comparación
            event_date = event.start.date() if event.start.date() else False
            
            # El evento es elegible si ocurrió entre el primer día del mes y hoy (inclusive)
            # Incluimos todos los eventos del día actual, independientemente de la hora
            event.is_in_current_month_until_today = (
                event_date and 
                first_day_of_month <= event_date <= today
            )
    
    @api.depends('start')
    def _compute_event_date_display(self):
        """Calcula una representación legible de la fecha del evento"""
        for event in self:
            if event.start:
                # Formato: "Lunes, 15 de Abril de 2023"
                event.event_date_display = event.start.strftime("%A, %d de %B de %Y").capitalize()
            else:
                event.event_date_display = False

    @api.depends('attendee_ids.has_participated')
    def _compute_participation_count(self):
        """Calcula el número y porcentaje de asistentes"""
        for event in self:
            total_attendees = len(event.attendee_ids)
            participants = len(event.attendee_ids.filtered('has_participated'))
            
            event.participation_count = participants
            event.participation_percentage = (participants / total_attendees) if total_attendees else 0

    def get_participation_status(self):
        """Devuelve el estado de asistencia para la API"""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'is_ongoing': self.is_ongoing,
            'is_in_current_month_until_today': self.is_in_current_month_until_today,
            'participation_count': self.participation_count,
            'participation_percentage': self.participation_percentage,
            'attendees': [{
                'id': attendee.id,
                'partner_id': attendee.partner_id.id,
                'partner_name': attendee.partner_id.name,
                'has_participated': attendee.has_participated,
                'can_mark_participation': attendee.can_mark_participation,
            } for attendee in self.attendee_ids]
        }

