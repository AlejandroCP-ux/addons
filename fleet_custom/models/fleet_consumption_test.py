# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FleetConsumptionTest(models.Model):
    _name = 'fleet.consumption.test'
    _description = 'Prueba de Consumo de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True)
    license_plate = fields.Char(string='Matrícula', related='vehicle_id.license_plate', readonly=True)
    is_technological = fields.Boolean(string='Es Vehículo Tecnológico', related='vehicle_id.is_technological', readonly=True)
    transport_consumption_index = fields.Float(string='Índice de Consumo según Prueba (Transporte)', tracking=True)
    tech_consumption_index = fields.Float(string='Índice de Consumo según Prueba (Tecnológico)', tracking=True)
    driver_id = fields.Many2one('res.partner', string='Chofer', required=True, tracking=True)
    kilometers_traveled = fields.Float(string='Kilómetros Recorridos', required=True, tracking=True)
    fuel_consumed = fields.Float(string='Combustible Consumido (Litros)', required=True, tracking=True)
    local_index = fields.Float(string='Índice Local', compute='_compute_indices', store=True, tracking=True)
    territory_index = fields.Float(string='Índice de Territorio', compute='_compute_indices', store=True, tracking=True)
    location = fields.Char(string='Lugar', tracking=True, required=True)
    observations = fields.Text(string='Observaciones', tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    @api.depends('vehicle_id', 'date')
    def _compute_name(self):
        for test in self:
            if test.vehicle_id and test.date:
                test.name = f"Prueba de Consumo - {test.vehicle_id.name} - {test.date}"
            else:
                test.name = "Nueva Prueba de Consumo"
    
    @api.depends('kilometers_traveled', 'fuel_consumed')
    def _compute_indices(self):
        for test in self:
            if test.fuel_consumed and test.fuel_consumed > 0:
                test.local_index = test.kilometers_traveled / test.fuel_consumed
            else:
                test.local_index = 0.0
            
            # Aquí puedes implementar la lógica para calcular el índice de territorio
            # Por ahora, lo dejamos igual al índice local
            test.territory_index = test.local_index
    
    def action_confirm(self):
        for record in self:
            # Verificar que los campos obligatorios estén completos
            if not record.location:
                raise ValidationError(_("Debe especificar el lugar donde se realizó la prueba."))
            
            # Verificar que los índices sean coherentes
            if record.is_technological and not record.tech_consumption_index:
                raise ValidationError(_("Debe especificar el índice de consumo tecnológico para vehículos tecnológicos."))
            
            if not record.transport_consumption_index:
                raise ValidationError(_("Debe especificar el índice de consumo de transporte."))
            
            record.write({'state': 'confirmed'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
    
    @api.constrains('date')
    def _check_date(self):
        for test in self:
            if test.date > fields.Date.today():
                raise ValidationError(_("La fecha de la prueba no puede ser futura."))
    
    @api.constrains('kilometers_traveled')
    def _check_kilometers_traveled(self):
        for test in self:
            if test.kilometers_traveled <= 0:
                raise ValidationError(_("Los kilómetros recorridos deben ser mayores que cero."))
    
    @api.constrains('fuel_consumed')
    def _check_fuel_consumed(self):
        for test in self:
            if test.fuel_consumed <= 0:
                raise ValidationError(_("El combustible consumido debe ser mayor que cero."))
    
    @api.constrains('transport_consumption_index', 'tech_consumption_index')
    def _check_consumption_indices(self):
        for test in self:
            if test.transport_consumption_index and test.transport_consumption_index <= 0:
                raise ValidationError(_("El índice de consumo de transporte debe ser mayor que cero."))
            
            if test.is_technological and test.tech_consumption_index and test.tech_consumption_index <= 0:
                raise ValidationError(_("El índice de consumo tecnológico debe ser mayor que cero."))
    
    def write(self, vals):
        # Verificar si se está intentando modificar una prueba confirmada o cancelada
        for record in self:
            if record.state in ['confirmed', 'cancelled'] and any(field not in ['state'] for field in vals.keys()):
                raise ValidationError(_("No puede modificar una prueba que está confirmada o cancelada."))
        return super(FleetConsumptionTest, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("No puede eliminar una prueba que no está en estado borrador."))
        return super(FleetConsumptionTest, self).unlink()
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            # Buscar la última prueba para este vehículo
            last_test = self.search([
                ('vehicle_id', '=', self.vehicle_id.id),
                ('state', '=', 'confirmed'),
                ('id', '!=', self.id)
            ], limit=1, order='date desc')
            
            if last_test:
                self.transport_consumption_index = last_test.transport_consumption_index
                self.tech_consumption_index = last_test.tech_consumption_index
                self.driver_id = last_test.driver_id
                self.location = last_test.location
    