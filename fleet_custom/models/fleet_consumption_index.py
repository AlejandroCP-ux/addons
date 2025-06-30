# -*- coding: utf-8 -*-

from odoo import models, fields, api

class FleetConsumptionIndex(models.Model):
    _name = 'fleet.consumption.index'
    _description = 'Índices de Consumo para Vehículos'
    _order = 'vehicle_id'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True)
    factory_consumption_index = fields.Float(string='Índice de Consumo de Fábrica (KM/L)')
    current_consumption_index = fields.Float(string='Índice de Consumo Actual (KM/L)')
    
    _sql_constraints = [
        ('vehicle_uniq', 'unique(vehicle_id)', 'Ya existe un registro para este vehículo!')
    ]
