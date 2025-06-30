# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class FleetFuelRecord(models.Model):
    _name = 'fleet.fuel.record'
    _description = 'Registro de Combustible y Kilómetros'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    name = fields.Char(string='Referencia', required=True, copy=False, default='Nuevo', tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True)
    license_plate = fields.Char(string='Matrícula', related='vehicle_id.license_plate', readonly=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    # Datos generales
    previous_odometer = fields.Float(string='Kilometraje Mes Anterior', required=True, tracking=True)
    estimated_fuel = fields.Float(string='Combustible Estimado en Tanque (Litros)', required=True, tracking=True)
    next_maintenance_odometer = fields.Float(string='Kilometraje Próximo Mantenimiento', required=True, tracking=True)
    planned_consumption_index = fields.Float(string='Índice de Consumo Plan (Km/L)', required=True, tracking=True)
    enabled_by = fields.Many2one('res.partner', string='Habilitado por', required=True, tracking=True, 
                                domain=[('is_company', '=', False)])
    
    # Datos de cierre
    closing_odometer = fields.Float(string='Kilometraje Cierre', tracking=True)
    closing_fuel = fields.Float(string='Combustible en Tanque al Cierre (Litros)', tracking=True)
    maintenance_odometer = fields.Float(string='Kilometraje Mantenimiento', tracking=True)
    
    # Campos calculados
    total_kilometers = fields.Float(string='Kilometraje Total', compute='_compute_totals', store=True, tracking=True)
    total_fuel_consumed = fields.Float(string='Combustible Total Consumido (Litros)', compute='_compute_totals', store=True, tracking=True)
    real_consumption_index = fields.Float(string='Índice de Consumo Real (Km/L)', compute='_compute_totals', store=True, tracking=True)
    consumption_percentage = fields.Float(string='Índice Consumo % Real/Plan', compute='_compute_totals', store=True, tracking=True)
    
    observations = fields.Text(string='Observaciones', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.fuel.record') or 'Nuevo'
        return super(FleetFuelRecord, self).create(vals_list)
    
    @api.depends('previous_odometer', 'closing_odometer', 'estimated_fuel', 'closing_fuel', 'planned_consumption_index')
    def _compute_totals(self):
        for record in self:
            # Kilometraje total
            record.total_kilometers = record.closing_odometer - record.previous_odometer if record.closing_odometer else 0
            
            # Combustible total consumido
            record.total_fuel_consumed = record.estimated_fuel - record.closing_fuel if record.closing_fuel is not None else 0
            
            # Índice de consumo real
            if record.total_fuel_consumed and record.total_fuel_consumed > 0:
                record.real_consumption_index = record.total_kilometers / record.total_fuel_consumed
            else:
                record.real_consumption_index = 0
            
            # Índice consumo % Real/Plan
            if record.planned_consumption_index and record.planned_consumption_index > 0:
                record.consumption_percentage = (record.real_consumption_index / record.planned_consumption_index) * 100
            else:
                record.consumption_percentage = 0
    
    def action_confirm(self):
        for record in self:
            if not record.closing_odometer or not record.closing_fuel:
                raise ValidationError(_("Debe completar los datos de cierre antes de confirmar."))
            
            if record.closing_odometer < record.previous_odometer:
                raise ValidationError(_("El kilometraje de cierre no puede ser menor que el kilometraje anterior."))
            
            record.write({'state': 'confirmed'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
    
    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date > fields.Date.today():
                raise ValidationError(_("La fecha no puede ser futura."))
    
    @api.constrains('previous_odometer', 'closing_odometer')
    def _check_odometer(self):
        for record in self:
            if record.closing_odometer and record.closing_odometer < record.previous_odometer:
                raise ValidationError(_("El kilometraje de cierre no puede ser menor que el kilometraje anterior."))
    
    @api.constrains('estimated_fuel', 'closing_fuel')
    def _check_fuel(self):
        for record in self:
            if record.estimated_fuel <= 0:
                raise ValidationError(_("El combustible estimado debe ser mayor que cero."))
            
            if record.closing_fuel is not None and record.closing_fuel < 0:
                raise ValidationError(_("El combustible al cierre no puede ser negativo."))
    
    def write(self, vals):
        # Verificar si se está intentando modificar un registro confirmado o cancelado
        for record in self:
            if record.state in ['confirmed', 'cancelled'] and any(field not in ['state', 'observations'] for field in vals.keys()):
                raise ValidationError(_("No puede modificar un registro que está confirmado o cancelado."))
        return super(FleetFuelRecord, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("No puede eliminar un registro que no está en estado borrador."))
        return super(FleetFuelRecord, self).unlink()
