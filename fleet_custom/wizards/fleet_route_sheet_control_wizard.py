# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta

class FleetRouteSheetControlWizard(models.TransientModel):
    _name = 'fleet.route.sheet.control.wizard'
    _description = 'Asistente para Control de Entrega de HR'
    
    date_from = fields.Date(string='Fecha desde', required=True, default=lambda self: fields.Date.today() - timedelta(days=30))
    date_to = fields.Date(string='Fecha hasta', required=True, default=fields.Date.today)
    
    def action_generate_report(self):
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'confirmed')
        ]
        
        return {
            'name': _('Control de Entrega de HR'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.route.sheet',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'search_default_confirmed': 1}
        }
