# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
import re
import logging
_logger = logging.getLogger(__name__)

class FuelMagneticCard(models.Model):
    _name = 'fuel.magnetic.card'
    _description = 'Tarjeta Magnética de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    name = fields.Char(string='Número de Tarjeta', required=True, copy=False, tracking=True,
                      help="Ingrese el número de 16 dígitos de la tarjeta")
    active = fields.Boolean(default=True, tracking=True)
    card_type = fields.Selection([
        ('vehicle', 'Vehículo'),
        ('generator', 'Generador'),
        ('other', 'Otro')
    ], string='Tipo de Tarjeta', required=True, default='vehicle', tracking=True)
    
    issue_date = fields.Date(string='Fecha de Emisión', default=fields.Date.context_today, required=True, tracking=True)
    expiry_date = fields.Date(string='Fecha de Vencimiento', required=True, tracking=True)
    
    supplier_id = fields.Many2one('fuel.supplier', string='Proveedor', required=True, tracking=True)
    carrier_id = fields.Many2one('fuel.carrier', string='Portador de Combustible', tracking=True,
                           help="Tipo de combustible asociado a esta tarjeta") 
    
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', tracking=True,
                                domain="[('active', '=', True)]")
    generator_id = fields.Many2one('fuel.power.generator', string='Generador', tracking=True)
    
    driver_id = fields.Many2one('fuel.driver', string='Conductor Asignado', tracking=True)
    holder_id = fields.Many2one('fuel.card.holder', string='Titular de la Tarjeta', tracking=True)
    
    pin = fields.Char(string='PIN', groups="fuel_card_management.group_fuel_card_manager", tracking=True)
    
    initial_balance = fields.Float(string='Saldo Inicial', default=0.0, tracking=True)
    current_balance = fields.Float(string='Saldo Actual', default=0.0, tracking=True)
    
    # Estados básicos - solo para manejo administrativo
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('available', 'Disponible'),
        ('assigned', 'Asignada'),
        ('expired', 'Vencida'),
        ('blocked', 'Bloqueada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True)
    
    # Campo computed para mostrar el estado de operación
    operational_state = fields.Selection([
        ('draft', 'Borrador'),
        ('available', 'Disponible'),
        ('assigned', 'Asignada'),
        ('expired', 'Vencida'),
        ('blocked', 'Bloqueada'),
        ('cancelled', 'Cancelada')
    ], string='Estado Operativo', compute='_compute_operational_state', store=True)
    
    # Campo para saber si está asignada por entrega
    is_delivered = fields.Boolean(string='Entregada', default=False, tracking=True)
    
    notes = fields.Text(string='Notas')
    
    load_ids = fields.One2many('fuel.card.load', 'card_id', string='Historial de Cargas')
    delivery_ids = fields.One2many('fuel.card.delivery', 'card_id', string='Historial de Entregas')
    ticket_ids = fields.One2many('fuel.ticket', 'card_id', string='Tickets de Combustible')
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El número de tarjeta debe ser único!')
    ]
    
    # Agregar más dependencias al campo computed
    @api.depends('state', 'is_delivered', 'holder_id', 'vehicle_id', 'generator_id')
    def _compute_operational_state(self):
        for card in self:
            if card.state in ['expired', 'blocked', 'cancelled', 'draft']:
                card.operational_state = card.state
            else:
                # Si está en estado normal, determinar si está disponible o asignada
                if card.is_delivered or card.holder_id or card.vehicle_id or card.generator_id:
                    card.operational_state = 'assigned'
                else:
                    card.operational_state = 'available'
    
    @api.constrains('name')
    def _check_card_number_format(self):
        """Validar que el número de tarjeta tenga exactamente 16 dígitos"""
        for card in self:
            if card.name:
                # Remover espacios para validar solo los dígitos
                clean_number = card.name.replace(' ', '')
                
                # Verificar que tenga exactamente 16 caracteres y que todos sean dígitos
                if not re.match(r'^\d{16}$', clean_number):
                    raise ValidationError(_("El número de tarjeta debe tener exactamente 16 dígitos numéricos."))
    
    @api.constrains('expiry_date')
    def _check_expiry_date(self):
        for card in self:
            if card.expiry_date and card.expiry_date < fields.Date.today():
                raise ValidationError(_("La fecha de vencimiento no puede ser anterior a la fecha actual."))
    
    def _format_card_number(self, number):
        """Formatear el número de tarjeta con espacios cada 4 dígitos"""
        if not number:
            return number
        
        # Remover espacios existentes y caracteres no numéricos
        clean_number = ''.join(filter(str.isdigit, number))
        
        # Limitar a 16 dígitos
        clean_number = clean_number[:16]
        
        # Agregar espacios cada 4 dígitos
        formatted = ' '.join([clean_number[i:i+4] for i in range(0, len(clean_number), 4)])
        
        return formatted
    
    @api.onchange('name')
    def _onchange_card_number(self):
        """Formatear automáticamente el número mientras se escribe"""
        if self.name:
            formatted_number = self._format_card_number(self.name)
            if formatted_number != self.name:
                self.name = formatted_number
    
    @api.model
    def create(self, vals):
        """Formatear el número antes de crear el registro y establecer estado inicial"""
        if vals.get('name'):
            vals['name'] = self._format_card_number(vals['name'])
        
        # Automáticamente pasar a disponible después de crear
        if vals.get('state') == 'draft':
            vals['state'] = 'available'
        
        return super(FuelMagneticCard, self).create(vals)
    
    def write(self, vals):
        """Formatear el número antes de actualizar el registro"""
        if vals.get('name'):
            vals['name'] = self._format_card_number(vals['name'])
        return super(FuelMagneticCard, self).write(vals)
    
    @api.onchange('card_type')
    def _onchange_card_type(self):
        self.vehicle_id = False
        self.generator_id = False
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and self.vehicle_id.driver_id:
            driver = self.env['fuel.driver'].search([('partner_id', '=', self.vehicle_id.driver_id.id)], limit=1)
            if driver:
                self.driver_id = driver.id
    
    # Métodos simplificados para manejo de estados administrativos
    def action_activate(self):
        """Activar tarjeta (de borrador a disponible)"""
        for card in self:
            if card.state == 'draft':
                card.write({
                    'state': 'available',
                    'is_delivered': False
                })
    
    def action_block(self):
        """Bloquear tarjeta"""
        for card in self:
            if card.state not in ['expired', 'cancelled']:
                card.state = 'blocked'
    
    def action_unblock(self):
        """Desbloquear tarjeta"""
        for card in self:
            if card.state == 'blocked':
                # Verificar si la tarjeta ha vencido mientras estaba bloqueada
                if card.expiry_date and card.expiry_date < fields.Date.today():
                    card.state = 'expired'
                else:
                    card.state = 'available'
    
    def action_cancel(self):
        """Cancelar tarjeta"""
        for card in self:
            if card.state != 'cancelled':
                card.write({
                    'state': 'cancelled',
                    'is_delivered': False,
                    'holder_id': False,
                    'driver_id': False,
                    'vehicle_id': False,
                    'generator_id': False
                })
    
    def action_reset_to_draft(self):
        """Volver a borrador"""
        for card in self:
            if card.state == 'cancelled':
                card.write({
                    'state': 'draft',
                    'is_delivered': False
                })
    
    # Métodos para manejo de entrega/devolución
    def _set_delivered(self, holder_id=False, driver_id=False, vehicle_id=False, generator_id=False):
        """Marcar tarjeta como entregada"""
        self.ensure_one()
        #Cambiar la condición para permitir desde 'available'
        if self.state in ['available', 'draft']:
            vals = {
                'is_delivered': True,
                'state': 'assigned',  
                'holder_id': holder_id,
                'driver_id': driver_id,
                'vehicle_id': vehicle_id,
                'generator_id': generator_id,
            }
            self.write(vals)
            # Forzar recálculo del campo computed
            self._compute_operational_state()
            
            # Log para debugging
            _logger.info(f"Tarjeta {self.name} entregada. Estado: {self.state}, Operativo: {self.operational_state}")
    
    def _set_returned(self):
        """Marcar tarjeta como devuelta"""
        self.ensure_one()
        # Verificar tanto el estado como el operational_state
        if self.state == 'assigned' or self.operational_state == 'assigned':
            vals = {
                'is_delivered': False,
                'state': 'available', 
                'holder_id': False,
                'driver_id': False,
                'vehicle_id': False,
                'generator_id': False,
            }
            self.write(vals)
            #  Forzar recálculo del campo computed
            self._compute_operational_state()
            
            # Log para debugging
            _logger.info(f"Tarjeta {self.name} devuelta. Estado: {self.state}, Operativo: {self.operational_state}")
    
    def can_be_delivered(self):
        """Verificar si la tarjeta puede ser entregada"""
        return self.operational_state == 'available' and self.state in ['available', 'draft']
    
    def can_be_returned(self):
        """Verificar si la tarjeta puede ser devuelta"""
        return self.operational_state == 'assigned' or self.state == 'assigned'
    
    @api.model
    def _cron_check_expired_cards(self):
        today = fields.Date.today()
        expired_cards = self.search([
            ('expiry_date', '<', today),
            ('state', 'in', ['available', 'assigned'])
        ])
        
        for card in expired_cards:
            card.state = 'expired'
            card.message_post(
                body=_("Esta tarjeta ha vencido automáticamente el %s.") % today,
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
    
    @api.model
    def _cron_notify_expiring_cards(self):
        today = fields.Date.today()
        expiry_warning_date = today + timedelta(days=30)  # Notificar 30 días antes
        
        expiring_cards = self.search([
            ('expiry_date', '>=', today),
            ('expiry_date', '<=', expiry_warning_date),
            ('state', 'in', ['available', 'assigned'])
        ])
        
        for card in expiring_cards:
            days_remaining = (card.expiry_date - today).days
            card.message_post(
                body=_("Esta tarjeta vencerá en %s días (el %s).") % (days_remaining, card.expiry_date),
                message_type='notification',
                subtype_xmlid='mail.mt_comment'
            )
            
            # Notificar al responsable de tarjetas
            managers = self.env.ref('fuel_card_management.group_fuel_card_manager').users
            if managers:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'note': _("La tarjeta %s vencerá en %s días (el %s).") % (card.name, days_remaining, card.expiry_date),
                    'user_id': managers[0].id,
                    'res_id': card.id,
                    'res_model_id': self.env['ir.model'].search([('model', '=', 'fuel.magnetic.card')], limit=1).id,
                })
    
    # Método para obtener datos del dashboard
    @api.model
    def get_dashboard_data(self):
        # Contar tarjetas por estado operativo
        available_cards = self.search_count([('operational_state', '=', 'available'), ('active', '=', True)])
        assigned_cards = self.search_count([('operational_state', '=', 'assigned'), ('active', '=', True)])
        expired_cards = self.search_count([('state', '=', 'expired'), ('active', '=', True)])
        blocked_cards = self.search_count([('state', '=', 'blocked'), ('active', '=', True)])
        
        # Calcular saldo total
        total_balance = sum(self.search([('active', '=', True)]).mapped('current_balance'))
        
        # Obtener consumo del mes actual
        today = fields.Date.today()
        first_day = today.replace(day=1)
        tickets = self.env['fuel.ticket'].search([
            ('date', '>=', first_day),
            ('date', '<=', today),
            ('state', '=', 'confirmed')
        ])
        month_consumption = sum(tickets.mapped('liters'))
        
        # Obtener planes pendientes de aprobación
        pending_plans = self.env['fuel.plan'].search_count([('state', '=', 'pending_approval')])
        
        # Obtener cargas recientes
        recent_loads = self.env['fuel.card.load'].search([
            ('state', '=', 'confirmed')
        ], limit=5, order='date desc')
        
        recent_loads_data = []
        for load in recent_loads:
            recent_loads_data.append({
                'id': load.id,
                'date': load.date,
                'card_name': load.card_id.name,
                'amount': load.amount
            })
        
        # Obtener tickets recientes
        recent_tickets = self.env['fuel.ticket'].search([
            ('state', '=', 'confirmed')
        ], limit=5, order='date desc')
        
        recent_tickets_data = []
        for ticket in recent_tickets:
            recent_tickets_data.append({
                'id': ticket.id,
                'date': ticket.date,
                'card_name': ticket.card_id.name,
                'liters': ticket.liters
            })
        
        return {
            'available_cards': available_cards,
            'assigned_cards': assigned_cards,
            'expired_cards': expired_cards,
            'blocked_cards': blocked_cards,
            'total_balance': total_balance,
            'month_consumption': month_consumption,
            'pending_plans': pending_plans,
            'recent_loads': recent_loads_data,
            'recent_tickets': recent_tickets_data
        }

