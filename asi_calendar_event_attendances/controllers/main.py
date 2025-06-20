# -*- coding: utf-8 -*-
# Parte de Odoo. Ver archivo LICENSE para detalles completos de licencia.

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.calendar.controllers.main import CalendarController
from odoo import fields
from odoo.http import request
from odoo.tools import get_lang
from datetime import timedelta

class CalendarParticipationController(http.Controller):
    
    @http.route('/calendar/participation/mark/<int:attendee_id>', type='json', auth='user')
    def mark_participation(self, attendee_id):
        """Marca la asistencia de un asistente"""
        attendee = request.env['calendar.attendee'].browse(attendee_id)
        
        # Verificar que el asistente existe
        if not attendee.exists():
            return {'error': _('El asistente no existe')}
        
        # Verificar que el usuario actual es el asistente
        if attendee.partner_id != request.env.user.partner_id:
            return {'error': _('Solo puedes marcar tu propia asistencia')}
        
        # Marcar asistencia
        result = attendee.mark_participation()
        
        return {
            'success': result,
            'message': _('Asistencia registrada correctamente') if result else _('No se pudo registrar la asistencia'),
            'data': attendee.get_participation_info()
        }
    
    @http.route('/calendar/participation/status/<int:event_id>', type='json', auth='user')
    def get_participation_status(self, event_id):
        """Obtiene el estado de asistencia de un evento"""
        event = request.env['calendar.event'].browse(event_id)
        
        # Verificar que el evento existe
        if not event.exists():
            return {'error': _('El evento no existe')}
        
        # Verificar que el usuario tiene acceso al evento
        try:
            event.check_access_rights('read')
            event.check_access_rule('read')
        except AccessError:
            return {'error': _('No tienes acceso a este evento')}
        
        return {
            'success': True,
            'data': event.get_participation_status()
        }

# Extender el controlador existente para añadir la funcionalidad de asistencia
class CalendarControllerExtended(CalendarController):
    
    @http.route('/calendar/meeting/view', type='http', auth="calendar")
    def view_meeting(self, token, id, **kwargs):
        """Extiende la vista de reunión para incluir información de asistencia"""
        response = super(CalendarControllerExtended, self).view_meeting(token, id, **kwargs)
        
        # Si la respuesta es un error o redirección, devolverla tal cual
        if not isinstance(response, http.Response) or response.status_code != 200:
            return response
        
        # Obtener el asistente y el evento
        attendee = request.env['calendar.attendee'].sudo().search([
            ('access_token', '=', token),
            ('event_id', '=', int(id))])
        
        if not attendee:
            return response
        
        # Verificar si el evento está en curso
        event = attendee.event_id
        now = fields.Datetime.today()+timedelta(days=1)
        is_ongoing = event.start <= now and event.stop >= now
        
        # Añadir información de asistencia al contexto
        context = {
            'is_ongoing': is_ongoing,
            'has_participated': attendee.has_participated,
            'can_mark_participation': is_ongoing ,# and not attendee.has_participated,
            'attendee_id': attendee.id,
        }
        
        # Renderizar la plantilla con el contexto adicional
        timezone = attendee.partner_id.tz
        lang = attendee.partner_id.lang or get_lang(request.env).code
        
        response_content = request.env['ir.ui.view'].with_context(lang=lang)._render_template(
            'calendar_participation.invitation_page_with_participation', {
                'company': event.user_id and event.user_id.company_id or event.create_uid.company_id,
                'event': event,
                'attendee': attendee,
                'participation': context,
            })
        
        return request.make_response(response_content, headers=[('Content-Type', 'text/html')])

