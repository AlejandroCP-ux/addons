# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FleetMaintenance(models.Model):
    _name = 'fleet.maintenance'
    _description = 'Mantenimientos de Vehículos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Referencia', required=True, copy=False, default='Nuevo', tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    maintenance_type = fields.Selection([
        ('preventive', 'Preventivo'),
        ('corrective', 'Correctivo'),
        ('diagnostic', 'Diagnóstico'),
        ('other', 'Otro')
    ], string='Tipo de Mantenimiento', required=True, tracking=True)
    is_scheduled = fields.Boolean(string='Programado', default=True, tracking=True)
    cause = fields.Text(string='Causa del Mantenimiento', required=True, tracking=True)
    description = fields.Text(string='Descripción', tracking=True)
    repair_parts = fields.Text(string='Piezas para Reparación', 
                              help='Especifique las piezas necesarias para la reparación',
                              tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('in_progress', 'En Progreso'),
        ('done', 'Realizado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', required=True, tracking=True)
    technician_id = fields.Many2one('res.users', string='Técnico Responsable', default=lambda self: self.env.user, tracking=True)
    cost = fields.Float(string='Costo', tracking=True)
    duration = fields.Float(string='Duración (horas)', tracking=True)
    
    # Campos para control de kilometraje
    odometer_before = fields.Float(string='Odómetro Antes', related='vehicle_id.odometer', readonly=True)
    reset_kilometers = fields.Boolean(string='Reiniciar Kilómetros Disponibles', default=True, help='Marque esta casilla para reiniciar los kilómetros disponibles a 5000 km')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.maintenance') or 'Nuevo'
        return super(FleetMaintenance, self).create(vals_list)
    
    def action_confirm(self):
        self.write({'state': 'confirmed'})
    
    def action_start(self):
        self.write({'state': 'in_progress'})
    
    def action_done(self):
        for record in self:
            # Actualizar la información de mantenimiento del vehículo
            values = {
                'last_maintenance_date': record.date,
                'last_maintenance_odometer': record.odometer_before,
            }
            
            # Si se marca para reiniciar kilómetros, establecer available_kilometers a 5000
            if record.reset_kilometers:
                values['available_kilometers'] = 5000.0
            
            record.vehicle_id.write(values)
            
            record.write({'state': 'done'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
