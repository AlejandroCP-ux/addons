# -*- coding: utf-8 -*-
# Parte de Odoo. Ver archivo LICENSE para detalles completos de licencia.

from datetime import datetime, timedelta, date
import calendar
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

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
        
    # Añadir campo de fecha para facilitar el filtrado
    event_date = fields.Date(
        string='Fecha del evento',
        compute='_compute_event_date',
        store=True,
        index=True,  # Indexar para mejorar rendimiento de búsquedas
        help='Fecha del evento (solo la fecha)')
        
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

    @api.depends('start')
    def _compute_event_date(self):
        """Calcula la fecha, mes y año del evento"""
        for event in self:
            if event.start:
                event_date = event.start.date()
                event.event_date = event_date
                event.event_month = event_date.month
                event.event_year = event_date.year
                _logger.info(f"Evento {event.id} - {event.name}: fecha={event_date}, mes={event_date.month}, año={event_date.year}")
            else:
                event.event_date = False
                event.event_month = False
                event.event_year = False

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
        return super(Meeting, self).search(args, offset, limit, order, count)
