# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError

class FleetNotificationSystem(models.Model):
    _name = 'fleet.notification.system'
    _description = 'Sistema de Notificaciones de Flota'

    @api.model
    def check_maintenance_alerts(self):
        """Verificar alertas de mantenimiento y crear notificaciones"""
        # Buscar vehículos que necesitan mantenimiento
        vehicles_needing_maintenance = self.env['fleet.vehicle'].search([
            ('available_kilometers', '<=', 1000),  # Menos de 1000 km disponibles
            ('maintenance_alert', '=', True)
        ])
        
        for vehicle in vehicles_needing_maintenance:
            # Verificar si ya existe una actividad pendiente para este vehículo
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'fleet.vehicle'),
                ('res_id', '=', vehicle.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('summary', 'ilike', 'Mantenimiento'),
                ('date_deadline', '>=', fields.Date.today())
            ])
            
            if not existing_activity:
                # Crear actividad de mantenimiento
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'Mantenimiento requerido para {vehicle.name}',
                    'note': f'El vehículo {vehicle.name} (Matrícula: {vehicle.license_plate}) '
                           f'necesita mantenimiento. Kilómetros disponibles: {vehicle.available_kilometers} km.',
                    'user_id': self.env.user.id,
                    'res_id': vehicle.id,
                    'res_model_id': self.env['ir.model'].search([('model', '=', 'fleet.vehicle')], limit=1).id,
                    'date_deadline': fields.Date.today() + timedelta(days=3),
                })
                
                # Enviar mensaje en el chatter del vehículo
                vehicle.message_post(
                    body=f"⚠️ <strong>Alerta de Mantenimiento</strong><br/>"
                         f"El vehículo necesita mantenimiento pronto.<br/>"
                         f"Kilómetros disponibles: {vehicle.available_kilometers} km",
                    subject="Alerta de Mantenimiento"
                )

    @api.model
    def check_ficav_alerts(self):
        """Verificar alertas de FICAV y crear notificaciones"""
        today = fields.Date.today()
        
        # Buscar vehículos con FICAV próximo a vencer (30 días)
        vehicles_ficav_alert = self.env['fleet.vehicle'].search([
            ('ficav_expiry_date', '<=', today + timedelta(days=30)),
            ('ficav_expiry_date', '>=', today),
            ('ficav_alert', '=', True)
        ])
        
        for vehicle in vehicles_ficav_alert:
            days_to_expiry = (vehicle.ficav_expiry_date - today).days
            
            # Verificar si ya existe una actividad pendiente para este vehículo
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'fleet.vehicle'),
                ('res_id', '=', vehicle.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('summary', 'ilike', 'FICAV'),
                ('date_deadline', '>=', fields.Date.today())
            ])
            
            if not existing_activity:
                # Crear actividad de renovación de FICAV
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'Renovar FICAV para {vehicle.name}',
                    'note': f'El FICAV del vehículo {vehicle.name} (Matrícula: {vehicle.license_plate}) '
                           f'vence en {days_to_expiry} días. Fecha de vencimiento: {vehicle.ficav_expiry_date}',
                    'user_id': self.env.user.id,
                    'res_id': vehicle.id,
                    'res_model_id': self.env['ir.model'].search([('model', '=', 'fleet.vehicle')], limit=1).id,
                    'date_deadline': vehicle.ficav_expiry_date - timedelta(days=7),
                })
                
                # Enviar mensaje en el chatter del vehículo
                vehicle.message_post(
                    body=f"📅 <strong>Alerta de FICAV</strong><br/>"
                         f"El FICAV vence en {days_to_expiry} días.<br/>"
                         f"Fecha de vencimiento: {vehicle.ficav_expiry_date}",
                    subject="Alerta de FICAV"
                )

    @api.model
    def check_scheduled_maintenance(self):
        """Verificar mantenimientos programados"""
        today = fields.Date.today()
        
        # Buscar mantenimientos programados para los próximos 7 días
        scheduled_maintenances = self.env['fleet.maintenance'].search([
            ('date', '<=', today + timedelta(days=7)),
            ('date', '>=', today),
            ('state', 'in', ['draft', 'confirmed']),
            ('is_scheduled', '=', True)
        ])
        
        for maintenance in scheduled_maintenances:
            days_to_maintenance = (maintenance.date - today).days
            
            # Verificar si ya existe una actividad pendiente para este mantenimiento
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'fleet.maintenance'),
                ('res_id', '=', maintenance.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('date_deadline', '>=', fields.Date.today())
            ])
            
            if not existing_activity:
                # Crear actividad de recordatorio de mantenimiento
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'Mantenimiento programado: {maintenance.name}',
                    'note': f'Mantenimiento programado para el vehículo {maintenance.vehicle_id.name} '
                           f'en {days_to_maintenance} días. Fecha: {maintenance.date}',
                    'user_id': maintenance.technician_id.id if maintenance.technician_id else self.env.user.id,
                    'res_id': maintenance.id,
                    'res_model_id': self.env['ir.model'].search([('model', '=', 'fleet.maintenance')], limit=1).id,
                    'date_deadline': maintenance.date,
                })

    @api.model
    def run_daily_checks(self):
        """Ejecutar todas las verificaciones diarias"""
        self.check_maintenance_alerts()
        self.check_ficav_alerts()
        self.check_scheduled_maintenance()
