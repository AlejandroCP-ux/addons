# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelPowerGenerator(models.Model):
    _name = 'fuel.power.generator'
    _description = 'Generador de Energía'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Nombre', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    serial_number = fields.Char(string='Número de Serie', tracking=True)
    model = fields.Char(string='Modelo', tracking=True)
    brand = fields.Char(string='Marca', tracking=True)
    
    location = fields.Char(string='Ubicación', tracking=True)
    department = fields.Char(string='Departamento', tracking=True)
    
    fuel_type = fields.Selection([
        ('diesel', 'Diesel'),
        ('gasoline', 'Gasolina'),
        ('other', 'Otro')
    ], string='Tipo de Combustible', default='diesel', required=True, tracking=True)
    
    tank_capacity = fields.Float(string='Capacidad del Tanque (L)', tracking=True)
    power = fields.Float(string='Potencia (kW)', tracking=True)
    
    purchase_date = fields.Date(string='Fecha de Compra', tracking=True)
    warranty_end_date = fields.Date(string='Fin de Garantía', tracking=True)
    
    card_ids = fields.One2many('fuel.magnetic.card', 'generator_id', string='Tarjetas Asignadas')
    card_count = fields.Integer(compute='_compute_card_count', string='Número de Tarjetas')
    
    consumption_ids = fields.One2many('fuel.ticket', 'generator_id', string='Consumo de Combustible')
    total_consumption = fields.Float(compute='_compute_total_consumption', string='Consumo Total (L)')
    
    notes = fields.Text(string='Notas')
    
    @api.depends('card_ids')
    def _compute_card_count(self):
        for generator in self:
            generator.card_count = len(generator.card_ids)
    
    @api.depends('consumption_ids')
    def _compute_total_consumption(self):
        for generator in self:
            generator.total_consumption = sum(generator.consumption_ids.filtered(lambda t: t.state == 'confirmed').mapped('liters'))
    
    @api.constrains('tank_capacity')
    def _check_tank_capacity(self):
        for generator in self:
            if generator.tank_capacity <= 0:
                raise ValidationError(_("La capacidad del tanque debe ser mayor que cero."))