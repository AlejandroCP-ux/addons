# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from datetime import datetime
from dateutil.relativedelta import relativedelta

class FleetKilometersReport(models.Model):
    _name = 'fleet.kilometers.report'
    _description = 'Informe de Kilómetros Totales Recorridos'
    _auto = False
    _order = 'total_kilometers desc'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', readonly=True)
    driver_id = fields.Many2one('res.partner', string='Chofer', readonly=True)
    license_plate = fields.Char(string='Matrícula', readonly=True)
    total_kilometers = fields.Float(string='Total Kilómetros Recorridos', readonly=True)
    total_trips = fields.Integer(string='Total de Viajes', readonly=True)
    date_from = fields.Date(string='Fecha Desde', readonly=True)
    date_to = fields.Date(string='Fecha Hasta', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () AS id,
                    rs.vehicle_id,
                    fv.driver_id,
                    fv.license_plate,
                    SUM(rs.total_kilometers) AS total_kilometers,
                    COUNT(rs.id) AS total_trips,
                    MIN(rs.date) AS date_from,
                    MAX(rs.date) AS date_to
                FROM fleet_route_sheet rs
                JOIN fleet_vehicle fv ON rs.vehicle_id = fv.id
                WHERE rs.state = 'confirmed'
                GROUP BY rs.vehicle_id, fv.driver_id, fv.license_plate
            )
        """ % self._table)

class FleetKilometersReportWizard(models.TransientModel):
    _name = 'fleet.kilometers.report.wizard'
    _description = 'Asistente para Informe de Kilómetros Totales'

    date_from = fields.Date(string='Fecha Desde', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Fecha Hasta', required=True, default=fields.Date.today)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo')
    driver_id = fields.Many2one('res.partner', string='Chofer', domain=[('is_company', '=', False)])

    def action_generate_report(self):
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'confirmed')
        ]
        
        if self.vehicle_id:
            domain.append(('vehicle_id', '=', self.vehicle_id.id))
        
        if self.driver_id:
            domain.append(('vehicle_id.driver_id', '=', self.driver_id.id))

        # Crear contexto para mostrar información del período
        context = {
            'search_default_confirmed': 1,
            'default_date_from': self.date_from,
            'default_date_to': self.date_to,
        }
        
        if not self.vehicle_id and not self.driver_id:
            context['group_by'] = ['vehicle_id', 'driver_id']

        return {
            'name': _('Kilómetros Totales Recorridos - %s a %s') % (self.date_from, self.date_to),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.route.sheet',
            'view_mode': 'tree',
            'view_id': self.env.ref('fleet_custom.view_fleet_route_sheet_kilometers_tree').id,
            'search_view_id': self.env.ref('fleet_custom.view_fleet_route_sheet_kilometers_search').id,
            'domain': domain,
            'context': context,
            'target': 'current',
        }
