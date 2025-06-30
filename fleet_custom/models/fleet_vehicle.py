# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class FleetVehicleInherit(models.Model):
    _inherit = 'fleet.vehicle'
    
    # Nuevos campos para el vehículo
    custom_fuel_type = fields.Selection([
        ('gasolina', 'Gasolina'),
        ('diesel', 'Diesel'),
        ('electrico', 'Eléctrico'),
        ('hibrido', 'Híbrido'),
        ('otro', 'Otro')
    ], string='Tipo de Combustible', help='Tipo de combustible que utiliza el vehículo')
    
    is_technological = fields.Boolean(
        string='Vehículo Tecnológico', 
        default=False,
        help='Marque esta casilla si el vehículo es de tipo tecnológico'
    )
    
    tech_fuel_type = fields.Selection([
        ('gasolina', 'Gasolina'),
        ('diesel', 'Diesel'),
        ('electrico', 'Eléctrico'),
        ('hibrido', 'Híbrido'),
        ('otro', 'Otro')
    ], string='Tipo de Combustible de Equipo Tecnológico', 
       help='Tipo de combustible que utiliza el equipo tecnológico')
    
    has_route_sheet = fields.Boolean(
        string='Posee Hoja de Ruta', 
        default=False,
        help='Marque esta casilla si el vehículo requiere hojas de ruta'
    )
    
    # Cambiado el nombre del campo para evitar conflictos
    custom_activity_type_id = fields.Many2one(
        'fleet.activity.type', 
        string='Tipo de Actividad',
        help='Tipo de actividad asociada al vehículo'
    )
    
    # Nuevo campo para número de circulación
    circulation_number = fields.Char(
        string='Número de Circulación',
        help='Número de circulación del vehículo'
    )
    
    # Nuevos campos para control de FICAV y kilómetros
    ficav_expiry_date = fields.Date(
        string='Vencimiento de FICAV',
        help='Fecha de vencimiento del FICAV'
    )
    
    available_kilometers = fields.Float(
        string='Kms Disponibles',
        help='Kilómetros disponibles hasta el próximo mantenimiento',
        default=5000.0
    )
    
    last_maintenance_date = fields.Date(
        string='Fecha Último Mantenimiento',
        help='Fecha del último mantenimiento realizado'
    )
    
    last_maintenance_odometer = fields.Float(
        string='Odómetro Último Mantenimiento',
        help='Lectura del odómetro en el último mantenimiento'
    )
    
    next_maintenance_odometer = fields.Float(
        string='Odómetro Próximo Mantenimiento',
        compute='_compute_next_maintenance_odometer',
        store=True,
        help='Lectura del odómetro para el próximo mantenimiento'
    )
    
    maintenance_alert = fields.Boolean(
        string='Alerta de Mantenimiento',
        compute='_compute_alerts',
        store=True,
        help='Indica si el vehículo está próximo a necesitar mantenimiento'
    )
    
    ficav_alert = fields.Boolean(
        string='Alerta de FICAV',
        compute='_compute_alerts',
        store=True,
        help='Indica si el FICAV está próximo a vencer'
    )
    
    maintenance_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Próximo'),
        ('alert', 'Urgente'),
        ('overdue', 'Vencido')
    ], string='Estado Mantenimiento', compute='_compute_alerts', store=True)
    
    ficav_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Próximo'),
        ('alert', 'Urgente'),
        ('expired', 'Vencido')
    ], string='Estado FICAV', compute='_compute_alerts', store=True)
    
    # Relaciones con los nuevos modelos
    route_sheet_ids = fields.One2many(
        'fleet.route.sheet', 
        'vehicle_id', 
        string='Hojas de Ruta',
        help='Hojas de ruta asociadas a este vehículo'
    )
    
    consumption_index_id = fields.One2many(
        'fleet.consumption.index', 
        'vehicle_id', 
        string='Índice de Consumo',
        help='Índices de consumo registrados para este vehículo'
    )
    
    fuel_ids = fields.One2many(
        'fleet.fuel', 
        'vehicle_id', 
        string='Registros de Combustible',
        help='Registros de combustible para este vehículo'
    )
    
    maintenance_ids = fields.One2many(
        'fleet.maintenance', 
        'vehicle_id', 
        string='Mantenimientos',
        help='Mantenimientos realizados a este vehículo'
    )
    
    @api.depends('last_maintenance_odometer')
    def _compute_next_maintenance_odometer(self):
        for vehicle in self:
            if vehicle.last_maintenance_odometer:
                vehicle.next_maintenance_odometer = vehicle.last_maintenance_odometer + 5000
            else:
                vehicle.next_maintenance_odometer = vehicle.odometer + 5000
    
    @api.depends('available_kilometers', 'ficav_expiry_date', 'next_maintenance_odometer', 'odometer')
    def _compute_alerts(self):
        today = fields.Date.today()
        for vehicle in self:
            # Alerta de mantenimiento
            if vehicle.available_kilometers <= 0:
                vehicle.maintenance_alert = True
                vehicle.maintenance_status = 'overdue'
            elif vehicle.available_kilometers <= 500:
                vehicle.maintenance_alert = True
                vehicle.maintenance_status = 'alert'
            elif vehicle.available_kilometers <= 1000:
                vehicle.maintenance_alert = True
                vehicle.maintenance_status = 'warning'
            else:
                vehicle.maintenance_alert = False
                vehicle.maintenance_status = 'ok'
            
            # Alerta de FICAV
            if vehicle.ficav_expiry_date:
                days_to_expiry = (vehicle.ficav_expiry_date - today).days
                if days_to_expiry < 0:
                    vehicle.ficav_alert = True
                    vehicle.ficav_status = 'expired'
                elif days_to_expiry <= 30:
                    vehicle.ficav_alert = True
                    vehicle.ficav_status = 'alert'
                elif days_to_expiry <= 90:
                    vehicle.ficav_alert = True
                    vehicle.ficav_status = 'warning'
                else:
                    vehicle.ficav_alert = False
                    vehicle.ficav_status = 'ok'
            else:
                vehicle.ficav_alert = False
                vehicle.ficav_status = 'ok'
    
    def action_schedule_maintenance(self):
        """Programar un mantenimiento para el vehículo"""
        self.ensure_one()
        return {
            'name': _('Programar Mantenimiento'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.maintenance',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_maintenance_type': 'preventive',
                'default_is_scheduled': True,
                'default_cause': 'Mantenimiento preventivo por kilometraje (5000 km)'
            }
        }
    
    def action_renew_ficav(self):
        """Abrir asistente para renovar FICAV"""
        self.ensure_one()
        return {
            'name': _('Renovar FICAV'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.ficav.renewal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_vehicle_id': self.id}
        }
    
    @api.onchange('is_technological')
    def _onchange_is_technological(self):
        if not self.is_technological:
            self.tech_fuel_type = False
        # Limpiar el tipo de actividad cuando cambia el tipo de vehículo
        self.custom_activity_type_id = False
    
    @api.onchange('is_technological')
    def _onchange_is_technological_activity(self):
        if self.is_technological:
            # Si es tecnológico, mostrar solo actividades para tecnológicos
            domain = [('is_for_technological', '=', True), ('active', '=', True)]
        else:
            # Si no es tecnológico, mostrar solo actividades para normales
            domain = [('is_for_technological', '=', False), ('active', '=', True)]
        
        return {'domain': {'custom_activity_type_id': domain}}
    
    @api.constrains('model_id')
    def _check_model_id(self):
        for record in self:
            if not record.model_id:
                raise ValidationError(_("Por favor, seleccione un modelo para el vehículo."))
    
    @api.constrains('license_plate')
    def _check_license_plate(self):
        for record in self:
            if not record.license_plate:
                raise ValidationError(_("Por favor, ingrese el número de matrícula del vehículo."))
    
    @api.constrains('circulation_number')
    def _check_circulation_number(self):
        for record in self:
            if not record.circulation_number:
                raise ValidationError(_("Por favor, ingrese el número de circulación del vehículo."))
    
    @api.constrains('driver_id')
    def _check_driver_id(self):
        for record in self:
            if not record.driver_id:
                raise ValidationError(_("Por favor, seleccione un conductor para el vehículo."))
    
    @api.constrains('is_technological', 'tech_fuel_type')
    def _check_tech_fuel_type(self):
        for record in self:
            if record.is_technological and not record.tech_fuel_type:
                raise ValidationError(_("Para vehículos tecnológicos, debe seleccionar un tipo de combustible."))
    
    @api.constrains('custom_activity_type_id')
    def _check_activity_type(self):
        for record in self:
            if not record.custom_activity_type_id:
                raise ValidationError(_("Por favor, seleccione un tipo de actividad para el vehículo."))
    
    @api.constrains('is_technological', 'custom_activity_type_id')
    def _check_activity_type_consistency(self):
        for record in self:
            if record.custom_activity_type_id:
                if record.is_technological and not record.custom_activity_type_id.is_for_technological:
                    raise ValidationError(_("Para vehículos tecnológicos debe seleccionar un tipo de actividad específico para vehículos tecnológicos."))
                elif not record.is_technological and record.custom_activity_type_id.is_for_technological:
                    raise ValidationError(_("Para vehículos normales debe seleccionar un tipo de actividad específico para vehículos normales."))
