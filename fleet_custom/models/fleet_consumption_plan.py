# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import calendar

class FleetConsumptionPlan(models.Model):
    _name = 'fleet.consumption.plan'
    _description = 'Plan de Consumo de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc, month desc'

    name = fields.Char(string='Referencia', compute='_compute_name', store=True)
    year = fields.Integer(string='Año', required=True, default=lambda self: datetime.now().year, tracking=True)
    month = fields.Selection([
        ('1', 'Enero'),
        ('2', 'Febrero'),
        ('3', 'Marzo'),
        ('4', 'Abril'),
        ('5', 'Mayo'),
        ('6', 'Junio'),
        ('7', 'Julio'),
        ('8', 'Agosto'),
        ('9', 'Septiembre'),
        ('10', 'Octubre'),
        ('11', 'Noviembre'),
        ('12', 'Diciembre')
    ], string='Mes', required=True, default=lambda self: str(datetime.now().month), tracking=True)
    total_fuel = fields.Float(string='Total de Combustible (Litros)', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    vehicle_allocation_ids = fields.One2many('fleet.consumption.plan.vehicle', 'plan_id', string='Asignación por Vehículos', tracking=True)
    activity_allocation_ids = fields.One2many('fleet.consumption.plan.activity', 'plan_id', string='Asignación por Actividades', tracking=True)
    total_allocated_vehicles = fields.Float(string='Total Asignado a Vehículos', compute='_compute_total_allocated', store=True)
    total_allocated_activities = fields.Float(string='Total Asignado a Actividades', compute='_compute_total_allocated', store=True)
    remaining_fuel_vehicles = fields.Float(string='Combustible Restante (Vehículos)', compute='_compute_remaining_fuel', store=True)
    remaining_fuel_activities = fields.Float(string='Combustible Restante (Actividades)', compute='_compute_remaining_fuel', store=True)
    
    @api.depends('year', 'month')
    def _compute_name(self):
        for plan in self:
            month_name = dict(self._fields['month'].selection).get(plan.month)
            plan.name = f"Plan de Consumo - {month_name} {plan.year}"
    
    @api.depends('vehicle_allocation_ids.allocated_fuel', 'activity_allocation_ids.allocated_fuel')
    def _compute_total_allocated(self):
        for plan in self:
            plan.total_allocated_vehicles = sum(line.allocated_fuel for line in plan.vehicle_allocation_ids)
            plan.total_allocated_activities = sum(line.allocated_fuel for line in plan.activity_allocation_ids)
    
    @api.depends('total_fuel', 'total_allocated_vehicles', 'total_allocated_activities')
    def _compute_remaining_fuel(self):
        for plan in self:
            plan.remaining_fuel_vehicles = plan.total_fuel - plan.total_allocated_vehicles
            plan.remaining_fuel_activities = plan.total_fuel - plan.total_allocated_activities
    
    @api.constrains('total_fuel')
    def _check_total_fuel(self):
        for plan in self:
            if plan.total_fuel <= 0:
                raise ValidationError(_("El total de combustible debe ser mayor que cero."))
    
    @api.constrains('year')
    def _check_year(self):
        for plan in self:
            current_year = datetime.now().year
            if plan.year < 2000 or plan.year > current_year + 5:
                raise ValidationError(_("El año debe estar entre 2000 y %s.", current_year + 5))
    
    @api.constrains('total_fuel', 'vehicle_allocation_ids', 'activity_allocation_ids')
    def _check_allocations(self):
        for plan in self:
            total_vehicle = sum(line.allocated_fuel for line in plan.vehicle_allocation_ids)
            total_activity = sum(line.allocated_fuel for line in plan.activity_allocation_ids)
            
            if total_vehicle > plan.total_fuel:
                raise ValidationError(_("La suma de combustible asignado a vehículos (%s) no puede superar el total disponible (%s)." % (total_vehicle, plan.total_fuel)))
            
            if total_activity > plan.total_fuel:
                raise ValidationError(_("La suma de combustible asignado a actividades (%s) no puede superar el total disponible (%s)." % (total_activity, plan.total_fuel)))
    
    def action_confirm(self):
        for record in self:
            # Verificar que haya al menos una asignación
            if not record.vehicle_allocation_ids and not record.activity_allocation_ids:
                raise ValidationError(_("Debe tener al menos una asignación de combustible antes de confirmar el plan."))
            
            record.write({'state': 'confirmed'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
    
    def get_days_in_month(self):
        return calendar.monthrange(self.year, int(self.month))[1]
    
    def write(self, vals):
        # Verificar si se está intentando modificar un plan confirmado o cancelado
        for record in self:
            if record.state in ['confirmed', 'cancelled'] and any(field not in ['state'] for field in vals.keys()):
                raise ValidationError(_("No puede modificar un plan que está confirmado o cancelado."))
        return super(FleetConsumptionPlan, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("No puede eliminar un plan que no está en estado borrador."))
        return super(FleetConsumptionPlan, self).unlink()
    
    @api.constrains('year', 'month')
    def _check_duplicate_plan(self):
        for plan in self:
            domain = [
                ('year', '=', plan.year),
                ('month', '=', plan.month),
                ('id', '!=', plan.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_("Ya existe un plan de consumo para %s %s." % (dict(self._fields['month'].selection).get(plan.month), plan.year)))

class FleetConsumptionPlanVehicle(models.Model):
    _name = 'fleet.consumption.plan.vehicle'
    _description = 'Asignación de Combustible por Vehículo'
    _order = 'vehicle_id'
    
    plan_id = fields.Many2one('fleet.consumption.plan', string='Plan de Consumo', required=True, ondelete='cascade')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True)
    allocated_fuel = fields.Float(string='Combustible Asignado (Litros)', required=True)
    
    _sql_constraints = [
        ('vehicle_plan_uniq', 'unique(plan_id, vehicle_id)', 'Ya existe una asignación para este vehículo en este plan!')
    ]
    
    @api.constrains('allocated_fuel')
    def _check_allocated_fuel(self):
        for line in self:
            if line.allocated_fuel <= 0:
                raise ValidationError(_("El combustible asignado debe ser mayor que cero."))
            
            # Verificar que no exceda el total disponible
            remaining = line.plan_id.total_fuel - sum(l.allocated_fuel for l in line.plan_id.vehicle_allocation_ids if l.id != line.id)
            if line.allocated_fuel > remaining:
                raise ValidationError(_("No puede asignar más combustible del disponible. Disponible: %s litros." % remaining))
    
    def write(self, vals):
        # Verificar si se está intentando modificar una asignación de un plan confirmado o cancelado
        for record in self:
            if record.plan_id.state in ['confirmed', 'cancelled']:
                raise ValidationError(_("No puede modificar una asignación de un plan que está confirmado o cancelado."))
        return super(FleetConsumptionPlanVehicle, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.plan_id.state != 'draft':
                raise ValidationError(_("No puede eliminar una asignación de un plan que no está en estado borrador."))
        return super(FleetConsumptionPlanVehicle, self).unlink()

class FleetConsumptionPlanActivity(models.Model):
    _name = 'fleet.consumption.plan.activity'
    _description = 'Asignación de Combustible por Actividad'
    _order = 'activity_type_id'
    
    plan_id = fields.Many2one('fleet.consumption.plan', string='Plan de Consumo', required=True, ondelete='cascade')
    activity_type_id = fields.Many2one('fleet.activity.type', string='Tipo de Actividad', required=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True)
    allocated_fuel = fields.Float(string='Combustible Asignado (Litros)', required=True)
    
    _sql_constraints = [
        ('activity_vehicle_plan_uniq', 'unique(plan_id, activity_type_id, vehicle_id)', 'Ya existe una asignación para esta actividad y vehículo en este plan!')
    ]
    
    @api.constrains('allocated_fuel')
    def _check_allocated_fuel(self):
        for line in self:
            if line.allocated_fuel <= 0:
                raise ValidationError(_("El combustible asignado debe ser mayor que cero."))
            
            # Verificar que no exceda el total disponible
            remaining = line.plan_id.total_fuel - sum(l.allocated_fuel for l in line.plan_id.activity_allocation_ids if l.id != line.id)
            if line.allocated_fuel > remaining:
                raise ValidationError(_("No puede asignar más combustible del disponible. Disponible: %s litros." % remaining))
    
    @api.constrains('vehicle_id', 'activity_type_id')
    def _check_vehicle_activity(self):
        for line in self:
            if line.vehicle_id.custom_activity_type_id and line.vehicle_id.custom_activity_type_id != line.activity_type_id:
                raise ValidationError(_("El vehículo %s está asignado a la actividad %s, no a %s." % (
                    line.vehicle_id.name, 
                    line.vehicle_id.custom_activity_type_id.name, 
                    line.activity_type_id.name
                )))
    
    def write(self, vals):
        # Verificar si se está intentando modificar una asignación de un plan confirmado o cancelado
        for record in self:
            if record.plan_id.state in ['confirmed', 'cancelled']:
                raise ValidationError(_("No puede modificar una asignación de un plan que está confirmado o cancelado."))
        return super(FleetConsumptionPlanActivity, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.plan_id.state != 'draft':
                raise ValidationError(_("No puede eliminar una asignación de un plan que no está en estado borrador."))
        return super(FleetConsumptionPlanActivity, self).unlink()
