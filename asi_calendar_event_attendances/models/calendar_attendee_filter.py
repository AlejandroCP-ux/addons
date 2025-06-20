# -*- coding: utf-8 -*-
# Parte de Odoo. Ver archivo LICENSE para detalles completos de licencia.

from odoo import api, models, fields
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from odoo import SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

class AttendeeFilter(models.Model):
    _inherit = 'calendar.attendee'

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """
        Extiende el método de búsqueda para filtrar automáticamente los asistentes
        mostrando solo los del mes actual o los que ya han participado
        """
        # Si estamos en la vista "Mi Asistencia a Eventos", aplicamos el filtro
        if self.env.context.get('default_has_participated') is False:
            # Verificar si es administrador
            is_admin = self.env.user.has_group("base.group_system") or self.env.user.id == SUPERUSER_ID
        
            # Si estamos en la vista de administrador, no aplicamos filtros adicionales
            if self.env.context.get('is_admin_view') and is_admin:
                return super(AttendeeFilter, self)._search(args, offset, limit, order, count, access_rights_uid)
        
            # Obtener el primer día del mes actual y el día actual
            today = date.today()+timedelta(days=1)
            first_day_of_month = date(today.year, today.month, 1)
        
            # Crear el dominio para filtrar eventos del mes actual o con participación
            # Incluimos todos los eventos del día actual, independientemente de la hora
            month_domain = [
                '&',
                ('event_id.active', '=', True),
                '|',
                ('has_participated', '=', True),
                '&',
                ('event_id.start', '>=', first_day_of_month.strftime('%Y-%m-%d 00:00:00')),
                ('event_id.start', '<=', today.strftime('%Y-%m-%d 23:59:59'))
            ]
        
            # Añadir este dominio a los argumentos existentes
            if args:
                args = ['&'] + list(args) + month_domain
            else:
                args = month_domain
        
        return super(AttendeeFilter, self)._search(args, offset, limit, order, count, access_rights_uid)
