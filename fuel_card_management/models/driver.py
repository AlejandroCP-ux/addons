# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class FuelDriver(models.Model):
    _name = 'fuel.driver'
    _description = 'Conductor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Nombre', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Contacto', required=True, tracking=True)
    
    license_number = fields.Char(string='Número de Licencia', tracking=True)
    license_type = fields.Selection([
        ('a', 'Tipo A'),
        ('b', 'Tipo B'),
        ('c', 'Tipo C'),
        ('d', 'Tipo D'),
        ('e', 'Tipo E'),
        ('other', 'Otro')
    ], string='Tipo de Licencia', tracking=True)
    license_expiry = fields.Date(string='Vencimiento de Licencia', tracking=True)
    
    department = fields.Char(string='Departamento', tracking=True)
    position = fields.Char(string='Cargo', tracking=True)
    
    vehicle_ids = fields.One2many('fleet.vehicle', 'driver_id', string='Vehículos Asignados')
    vehicle_count = fields.Integer(compute='_compute_vehicle_count', string='Número de Vehículos')
    
    card_ids = fields.One2many('fuel.magnetic.card', 'driver_id', string='Tarjetas Asignadas')
    card_count = fields.Integer(compute='_compute_card_count', string='Número de Tarjetas')
    
    consumption_ids = fields.One2many('fuel.ticket', 'driver_id', string='Consumo de Combustible')
    total_consumption = fields.Float(compute='_compute_total_consumption', string='Consumo Total (L)')
    
    notes = fields.Text(string='Notas')
    
    _sql_constraints = [
        ('partner_uniq', 'unique(partner_id)', 'Ya existe un conductor para este contacto!')
    ]
    
    @api.depends('vehicle_ids')
    def _compute_vehicle_count(self):
        for driver in self:
            driver.vehicle_count = len(driver.vehicle_ids)
    
    @api.depends('card_ids')
    def _compute_card_count(self):
        for driver in self:
            driver.card_count = len(driver.card_ids)
    
    @api.depends('consumption_ids')
    def _compute_total_consumption(self):
        for driver in self:
            driver.total_consumption = sum(driver.consumption_ids.filtered(lambda t: t.state == 'confirmed').mapped('liters'))