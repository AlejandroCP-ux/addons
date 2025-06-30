# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FleetFuel(models.Model):
    _name = 'fleet.fuel'
    _description = 'Registro de Combustible'
    _order = 'date desc'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True)
    tank_liters = fields.Float(string='Litros en Tanque', required=True)
    enabled_by = fields.Many2one('res.partner', string='Habilitado por', required=True)
    
    @api.constrains('tank_liters')
    def _check_tank_liters(self):
        for record in self:
            if record.tank_liters <= 0:
                raise ValidationError(_("La cantidad de litros debe ser mayor que cero."))
    
    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date > fields.Date.today():
                raise ValidationError(_("La fecha no puede ser futura."))
