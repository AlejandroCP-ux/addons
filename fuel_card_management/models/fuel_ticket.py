# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class FuelTicket(models.Model):
    _name = 'fuel.ticket'
    _description = 'Ticket de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, day_sequence desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
   
    day_sequence = fields.Integer(string='Secuencia del Día', default=1,
                                 help="Orden del ticket dentro del mismo día")
    
    card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True, tracking=True,
                             domain="[('state', '=', 'assigned')]")
    
    # Campo relacionado para obtener el tipo de tarjeta
    card_type = fields.Selection(related='card_id.card_type', string='Tipo de Tarjeta', readonly=True, store=True)
    
    carrier_id = fields.Many2one(related='card_id.carrier_id', string='Portador', readonly=True, store=True)
    supplier_id = fields.Many2one('fuel.supplier', string='Proveedor', related='card_id.supplier_id', readonly=True)
    
    # Campos de asignación según tipo de tarjeta
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', tracking=True)
    generator_id = fields.Many2one('fuel.power.generator', string='Generador', tracking=True)
    driver_id = fields.Many2one('fuel.driver', string='Conductor', tracking=True)
    
    # Campos de responsables
    vehicle_responsible_id = fields.Many2one('res.partner', string='Responsable del Vehículo', tracking=True)
    generator_responsible_id = fields.Many2one('res.partner', string='Responsable del Generador', tracking=True)
    general_responsible_id = fields.Many2one('res.partner', string='Responsable General', tracking=True)
    
    # Campos financieros
    initial_balance = fields.Float(string='Saldo Inicial', readonly=True, tracking=True)
    liters = fields.Float(string='Litros', required=True, tracking=True)
    unit_price = fields.Float(string='Precio Unitario', readonly=True, tracking=True,
                              help="Precio por litro tomado automáticamente del portador de combustible")
    amount = fields.Float(string='Importe', compute='_compute_amount', store=True, tracking=True)
    final_balance = fields.Float(string='Saldo Final', compute='_compute_final_balance', store=True, tracking=True)
    
    # Campos de odómetro y consumo (solo para vehículos)
    odometer = fields.Float(string='Odómetro Actual', tracking=True)
    previous_odometer = fields.Float(string='Odómetro Anterior', compute='_compute_odometer_data', store=True)
    distance_traveled = fields.Float(string='Distancia Recorrida (km)', compute='_compute_odometer_data', store=True)
    fuel_efficiency = fields.Float(string='Eficiencia (L/100km)', compute='_compute_fuel_efficiency', store=True)
    estimated_range = fields.Float(string='Autonomía Estimada (km)', compute='_compute_estimated_range', store=True)
    
    # CAMPOS PARA CONTROL DE COMBUSTIBLE 
    fuel_consumed = fields.Float(string='Combustible Consumido (L)', compute='_compute_fuel_consumed', store=True,
                                help="Combustible consumido basado en la distancia recorrida y eficiencia del vehículo")
    remaining_fuel_before = fields.Float(string='Combustible Restante Antes (L)', compute='_compute_remaining_fuel', store=True,
                                       help="Combustible estimado que quedaba en el tanque antes de esta carga")
    current_fuel_in_tank = fields.Float(string='Combustible Actual en Tanque (L)', compute='_compute_current_fuel_in_tank', store=True,
                                      help="Combustible actual en el tanque (igual que remaining_fuel_before)")
    fuel_after_fill = fields.Float(string='Combustible Después de Carga (L)', compute='_compute_fuel_after_fill', store=True,
                                  help="Combustible total después de cargar (restante + cargado)")
    tank_capacity_exceeded = fields.Boolean(string='Excede Capacidad', compute='_compute_tank_capacity_check', store=True,
                                          help="Indica si la carga excede la capacidad del tanque")
    tank_fill_type = fields.Selection([
        ('partial', 'Carga Parcial'),
        ('full', 'Tanque Lleno'),
        ('overflow', 'Excede Capacidad')
    ], string='Tipo de Carga', compute='_compute_tank_fill_type', store=True)
    
    # Información técnica del vehículo (campos relacionados)
    vehicle_fuel_type = fields.Many2one(related='vehicle_id.fuel_type', string='Tipo de Combustible', readonly=True)
    vehicle_tank_capacity = fields.Float(related='vehicle_id.tank_capacity', string='Capacidad del Tanque', readonly=True)
    vehicle_avg_consumption = fields.Float(related='vehicle_id.average_consumption', string='Consumo Promedio', readonly=True)
    tank_fill_percentage = fields.Float(string='% Llenado del Tanque', compute='_compute_tank_fill_percentage', store=True)
    
    # Campo para indicar si es el primer ticket del vehículo
    is_first_ticket = fields.Boolean(string='Primer Ticket', compute='_compute_is_first_ticket', store=True)
    
    # Campo para combustible inicial manual (OBLIGATORIO para primer ticket)
    initial_fuel_manual = fields.Float(string='Combustible Inicial (L)', 
                                     help="Combustible inicial en el tanque. OBLIGATORIO para el primer ticket del vehículo")
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    notes = fields.Text(string='Notas')

    @api.onchange('card_id', 'date')
    def _onchange_day_sequence(self):
        """Actualiza la secuencia del día dinámicamente al cambiar tarjeta o fecha"""
        if self.card_id and self.date:
            domain = [
                ('card_id', '=', self.card_id.id),
                ('date', '=', self.date),
            ]
        
            # Solo excluir el registro actual si ya tiene un ID real (no temporal)
            if isinstance(self.id, int):
                domain.append(('id', '!=', self.id))
            
            same_day_tickets = self.env['fuel.ticket'].search(domain)
            self.day_sequence = len(same_day_tickets) + 1
            _logger.debug(f"[ONCHANGE] Nueva secuencia calculada: {self.day_sequence} para tarjeta {self.card_id.name} en {self.date}")
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.ticket') or _('Nuevo')
        
        # Obtener información de la tarjeta
        if vals.get('card_id'):
            card = self.env['fuel.magnetic.card'].browse(vals['card_id'])
            
            # Calcular saldo inicial considerando tickets del mismo día
            ticket_date = vals.get('date', fields.Date.today())
            initial_balance = self._get_initial_balance_for_card(card, ticket_date)
            vals['initial_balance'] = initial_balance
            
            # Asignar secuencia del día
            vals['day_sequence'] = self._get_next_day_sequence(card, ticket_date)
            
            # Obtener precio actual del portador si no se especifica
            if not vals.get('unit_price') and card.carrier_id:
                vals['unit_price'] = card.carrier_id.current_price
            
            # Obtener información según el tipo de tarjeta
            if card.card_type == 'vehicle' and card.vehicle_id:
                vals.update({
                    'vehicle_id': card.vehicle_id.id,
                    'driver_id': card.driver_id.id if card.driver_id else False,
                    'vehicle_responsible_id': card.holder_id.partner_id.id if card.holder_id and card.holder_id.partner_id else False,
                })
                # Obtener odómetro actual del vehículo si no se especifica
                if not vals.get('odometer'):
                    vals['odometer'] = card.vehicle_id.odometer
                    
            elif card.card_type == 'generator' and card.generator_id:
                vals.update({
                    'generator_id': card.generator_id.id,
                    'generator_responsible_id': card.holder_id.partner_id.id if card.holder_id and card.holder_id.partner_id else False,
                })
                
            elif card.card_type == 'other':
                vals['general_responsible_id'] = card.holder_id.partner_id.id if card.holder_id and card.holder_id.partner_id else False
        
        return super(FuelTicket, self).create(vals)
    
    def _get_initial_balance_for_card(self, card, ticket_date):
        """
        Calcula el saldo inicial correcto considerando tickets del mismo día
        """
        # Buscar el último ticket confirmado de esta tarjeta hasta la fecha 
        last_ticket = self.env['fuel.ticket'].search([
            ('card_id', '=', card.id),
            ('state', '=', 'confirmed'),
            ('date', '<=', ticket_date),
        ], order='date desc, day_sequence desc, id desc', limit=1)
        
        if last_ticket:
            # Si hay un ticket anterior, usar su saldo final
            _logger.debug(f"Using balance from previous ticket {last_ticket.id}: {last_ticket.final_balance}")
            return last_ticket.final_balance
        else:
            # Si no hay tickets anteriores, usar el saldo actual de la tarjeta
            _logger.debug(f"Using card current balance: {card.current_balance}")
            return card.current_balance
    
    def _get_next_day_sequence(self, card, ticket_date):
        """
        Obtiene la siguiente secuencia para tickets del mismo día
        """
        # Buscar tickets del mismo día para esta tarjeta
        same_day_tickets = self.env['fuel.ticket'].search([
            ('card_id', '=', card.id),
            ('date', '=', ticket_date),
        ], order='day_sequence desc', limit=1)
        
        if same_day_tickets:
            next_sequence = same_day_tickets.day_sequence + 1
            _logger.debug(f"Next day sequence for card {card.id} on {ticket_date}: {next_sequence}")
            return next_sequence
        else:
            _logger.debug(f"First ticket of the day for card {card.id} on {ticket_date}")
            return 1
    
    def _get_previous_ticket(self, vehicle_id, date, exclude_id=None):
        """
        Busca el ticket anterior considerando múltiples tickets del mismo día
        """
        domain = [
            ('vehicle_id', '=', vehicle_id),
            ('state', '=', 'confirmed'),
        ]
        
        # Si hay un ID a excluir (para evitar auto-referencia)
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        
        # Buscar primero en fechas anteriores
        previous_date_ticket = self.env['fuel.ticket'].search(
            domain + [('date', '<', date)],
            order='date desc, day_sequence desc, id desc', 
            limit=1
        )
        
        # Luego buscar en el mismo día con secuencia menor
        current_day_sequence = getattr(self, 'day_sequence', 1)
        same_day_ticket = self.env['fuel.ticket'].search(
            domain + [
                ('date', '=', date),
                ('day_sequence', '<', current_day_sequence)
            ],
            order='day_sequence desc, id desc', 
            limit=1
        )
        
        # Retornar el más reciente entre ambos
        if previous_date_ticket and same_day_ticket:
            if (previous_date_ticket.date > same_day_ticket.date or 
                (previous_date_ticket.date == same_day_ticket.date and 
                 previous_date_ticket.day_sequence > same_day_ticket.day_sequence)):
                return previous_date_ticket
            else:
                return same_day_ticket
        elif previous_date_ticket:
            return previous_date_ticket
        elif same_day_ticket:
            return same_day_ticket
        else:
            return self.env['fuel.ticket']
    
    @api.depends('liters', 'unit_price')
    def _compute_amount(self):
        for ticket in self:
            ticket.amount = ticket.liters * ticket.unit_price
    
    @api.depends('initial_balance', 'amount')
    def _compute_final_balance(self):
        for ticket in self:
            ticket.final_balance = ticket.initial_balance - ticket.amount
    
    @api.depends('vehicle_id', 'date', 'day_sequence')
    def _compute_is_first_ticket(self):
        for ticket in self:
            if ticket.vehicle_id:
                # Buscar tickets anteriores confirmados para este vehículo
                previous_tickets = self.env['fuel.ticket'].search([
                    ('vehicle_id', '=', ticket.vehicle_id.id),
                    ('state', '=', 'confirmed'),
                    '|',
                        ('date', '<', ticket.date or fields.Date.context_today),
                        '&',
                            ('date', '=', ticket.date or fields.Date.context_today),
                            ('day_sequence', '<', ticket.day_sequence),
                ], limit=1)
                ticket.is_first_ticket = not bool(previous_tickets)
                _logger.debug(f"Ticket {ticket.id} (seq: {ticket.day_sequence}) is_first_ticket: {ticket.is_first_ticket}")
            else:
                ticket.is_first_ticket = False
    
    @api.depends('vehicle_id', 'odometer', 'date', 'day_sequence')
    def _compute_odometer_data(self):
        for ticket in self:
            if ticket.vehicle_id and ticket.odometer:
                #  Usar método  para buscar ticket anterior
                previous_ticket = ticket._get_previous_ticket(
                    ticket.vehicle_id.id,
                    ticket.date or fields.Date.context_today(),
                    ticket.id if isinstance(ticket.id, int) else None
                )
                
                if previous_ticket:
                    ticket.previous_odometer = previous_ticket.odometer
                    ticket.distance_traveled = max(0, ticket.odometer - previous_ticket.odometer)
                    _logger.debug(f"Ticket {ticket.id} - Previous odometer: {previous_ticket.odometer} from ticket {previous_ticket.id} (seq: {previous_ticket.day_sequence})")
                else:
                    ticket.previous_odometer = 0
                    ticket.distance_traveled = 0
                    _logger.debug(f"Ticket {ticket.id} - No previous ticket found")
            else:
                ticket.previous_odometer = 0
                ticket.distance_traveled = 0
    
    @api.depends('distance_traveled', 'vehicle_avg_consumption')
    def _compute_fuel_consumed(self):
        for ticket in self:
            if ticket.distance_traveled > 0 and ticket.vehicle_avg_consumption > 0:
                ticket.fuel_consumed = (ticket.distance_traveled * ticket.vehicle_avg_consumption) / 100
                _logger.debug(f"Ticket {ticket.id} - Fuel consumed: {ticket.fuel_consumed} (distance: {ticket.distance_traveled}, avg: {ticket.vehicle_avg_consumption})")
            else:
                ticket.fuel_consumed = 0
    
    @api.depends('fuel_consumed', 'is_first_ticket', 'vehicle_tank_capacity', 'initial_fuel_manual', 'date', 'day_sequence')
    def _compute_remaining_fuel(self):
        for ticket in self:
            if ticket.card_type == 'vehicle' and ticket.vehicle_id:
                if ticket.is_first_ticket:
                    # Para el primer ticket, usar el valor manual obligatorio
                    ticket.remaining_fuel_before = max(0, ticket.initial_fuel_manual - ticket.fuel_consumed)
                    _logger.debug(f"Ticket {ticket.id} - First ticket with manual fuel: {ticket.initial_fuel_manual}")
                else:
                    # CORREGIDO: Buscar el ticket anterior considerando mismo día
                    previous_ticket = ticket._get_previous_ticket(
                        ticket.vehicle_id.id,
                        ticket.date or fields.Date.context_today(),
                        ticket.id if isinstance(ticket.id, int) else None
                    )
                    
                    if previous_ticket:
                        ticket.remaining_fuel_before = max(0, previous_ticket.fuel_after_fill - ticket.fuel_consumed)
                        _logger.debug(f"Ticket {ticket.id} - Previous ticket found: {previous_ticket.id} (seq: {previous_ticket.day_sequence}), fuel_after_fill: {previous_ticket.fuel_after_fill}")
                    else:
                        # Si no hay tickets anteriores pero no es el primero, algo anda mal
                        ticket.remaining_fuel_before = 0
                        _logger.warning(f"Ticket {ticket.id} - No previous ticket found but is_first_ticket is False")
            else:
                ticket.remaining_fuel_before = 0
    
    @api.depends('remaining_fuel_before')
    def _compute_current_fuel_in_tank(self):
        for ticket in self:
            ticket.current_fuel_in_tank = ticket.remaining_fuel_before
    
    @api.depends('remaining_fuel_before', 'liters')
    def _compute_fuel_after_fill(self):
        for ticket in self:
            ticket.fuel_after_fill = ticket.remaining_fuel_before + ticket.liters
            _logger.debug(f"Ticket {ticket.id} - Fuel after fill: {ticket.fuel_after_fill} (before: {ticket.remaining_fuel_before}, liters: {ticket.liters})")
    
    @api.depends('fuel_after_fill', 'vehicle_tank_capacity')
    def _compute_tank_capacity_check(self):
        for ticket in self:
            if ticket.card_type == 'vehicle' and ticket.vehicle_tank_capacity > 0:
                ticket.tank_capacity_exceeded = ticket.fuel_after_fill > (ticket.vehicle_tank_capacity + 15)
            else:
                ticket.tank_capacity_exceeded = False
    
    @api.depends('fuel_after_fill', 'vehicle_tank_capacity', 'tank_capacity_exceeded')
    def _compute_tank_fill_type(self):
        for ticket in self:
            if ticket.card_type == 'vehicle' and ticket.vehicle_tank_capacity > 0:
                if ticket.tank_capacity_exceeded:
                    ticket.tank_fill_type = 'overflow'
                elif abs(ticket.fuel_after_fill - ticket.vehicle_tank_capacity) <= 10:
                    ticket.tank_fill_type = 'full'
                else:
                    ticket.tank_fill_type = 'partial'
            else:
                ticket.tank_fill_type = 'partial'
    
    @api.depends('liters', 'distance_traveled')
    def _compute_fuel_efficiency(self):
        for ticket in self:
            if ticket.distance_traveled > 0 and ticket.liters > 0:
                ticket.fuel_efficiency = (ticket.liters * 100) / ticket.distance_traveled
            else:
                ticket.fuel_efficiency = 0
    
    @api.depends('fuel_after_fill', 'vehicle_tank_capacity')
    def _compute_tank_fill_percentage(self):
        for ticket in self:
            if ticket.vehicle_tank_capacity > 0:
                ticket.tank_fill_percentage = min(100, (ticket.fuel_after_fill / ticket.vehicle_tank_capacity) * 100)
            else:
                ticket.tank_fill_percentage = 0
    
    @api.depends('liters', 'vehicle_avg_consumption')
    def _compute_estimated_range(self):
        for ticket in self:
            if ticket.vehicle_avg_consumption > 0:
                ticket.estimated_range = ticket.liters * (100 / ticket.vehicle_avg_consumption)
            else:
                ticket.estimated_range = 0
    
    @api.onchange('card_id')
    def _onchange_card_id(self):
        if self.card_id:
            # Usar método para calcular saldo inicial correcto
            self.initial_balance = self._get_initial_balance_for_card(
                self.card_id, 
                self.date or fields.Date.context_today()
            )
            
            # Limpiar campos anteriores
            self.vehicle_id = False
            self.generator_id = False
            self.driver_id = False
            self.vehicle_responsible_id = False
            self.generator_responsible_id = False
            self.general_responsible_id = False
            self.odometer = 0
            self.initial_fuel_manual = 0
            
            # Asignar según el tipo de tarjeta
            if self.card_id.card_type == 'vehicle':
                self.vehicle_id = self.card_id.vehicle_id
                self.driver_id = self.card_id.driver_id
                if self.card_id.holder_id and self.card_id.holder_id.partner_id:
                    self.vehicle_responsible_id = self.card_id.holder_id.partner_id
                if self.vehicle_id:
                    self.odometer = self.vehicle_id.odometer
                    
            elif self.card_id.card_type == 'generator':
                self.generator_id = self.card_id.generator_id
                if self.card_id.holder_id and self.card_id.holder_id.partner_id:
                    self.generator_responsible_id = self.card_id.holder_id.partner_id
                
            elif self.card_id.card_type == 'other':
                if self.card_id.holder_id and self.card_id.holder_id.partner_id:
                    self.general_responsible_id = self.card_id.holder_id.partner_id
            
            # Actualizar precio unitario
            if self.card_id.carrier_id:
                self.unit_price = self.card_id.carrier_id.current_price
    
    @api.onchange('date', 'card_id')
    def _onchange_date_card(self):
        """Recalcular saldo inicial cuando cambia la fecha o tarjeta"""
        if self.card_id and self.date:
            self.initial_balance = self._get_initial_balance_for_card(self.card_id, self.date)
    
    @api.onchange('liters')
    def _onchange_calculate_amount(self):
        if self.liters and self.unit_price:
            self.amount = self.liters * self.unit_price
    
    @api.onchange('odometer', 'liters')
    def _onchange_fuel_validation(self):
        if self.card_type == 'vehicle' and self.vehicle_id and self.odometer and self.liters:
            if self.tank_capacity_exceeded and (self.fuel_after_fill - self.vehicle_tank_capacity) > 20:
                return {
                    'warning': {
                        'title': _('Advertencia: Capacidad del Tanque Muy Excedida'),
                        'message': _(
                            'La carga de combustible excede significativamente la capacidad del tanque:\n'
                            '• Combustible restante estimado: %.2f L\n'
                            '• Combustible a cargar: %.2f L\n'
                            '• Total después de carga: %.2f L\n'
                            '• Capacidad del tanque: %.2f L\n'
                            '• Exceso: %.2f L\n\n'
                            'Considere verificar los datos si el exceso es muy grande.'
                        ) % (
                            self.remaining_fuel_before,
                            self.liters,
                            self.fuel_after_fill,
                            self.vehicle_tank_capacity,
                            self.fuel_after_fill - self.vehicle_tank_capacity
                        )
                    }
                }
    
    @api.constrains('liters', 'amount', 'card_id')
    def _check_balance(self):
        for ticket in self:
            if ticket.amount > ticket.initial_balance:
                raise ValidationError(_("El importe del ticket no puede ser mayor que el saldo de la tarjeta."))
    
    @api.constrains('liters')
    def _check_positive_values(self):
        for ticket in self:
            if ticket.liters <= 0:
                raise ValidationError(_("La cantidad de litros debe ser mayor que cero."))
    
    @api.constrains('odometer', 'vehicle_id')
    def _check_odometer(self):
        for ticket in self:
            if ticket.card_type == 'vehicle' and ticket.vehicle_id:
                if not ticket.odometer or ticket.odometer <= 0:
                    raise ValidationError(_("El odómetro es obligatorio para tickets de vehículos y debe ser mayor que cero."))
                
                if ticket.previous_odometer and ticket.odometer < ticket.previous_odometer:
                    self.env['ir.logging'].create({
                        'name': 'fuel.ticket',
                        'type': 'server',
                        'level': 'WARNING',
                        'message': _("Odómetro actual (%s) menor que el anterior (%s) en ticket %s") % 
                                 (ticket.odometer, ticket.previous_odometer, ticket.name),
                        'path': 'fuel_ticket',
                        'func': '_check_odometer',
                        'line': '1'
                    })
    
    @api.constrains('initial_fuel_manual', 'is_first_ticket', 'card_type', 'vehicle_id')
    def _check_initial_fuel_manual(self):
        """Validar que el combustible inicial sea obligatorio para el primer ticket de vehículo"""
        for ticket in self:
            if (ticket.card_type == 'vehicle' and 
                ticket.vehicle_id and 
                ticket.is_first_ticket and 
                ticket.initial_fuel_manual <= 0):
                raise ValidationError(_(
                    "El campo 'Combustible Inicial' es obligatorio para el primer ticket del vehículo '%s'.\n"
                    "Debe especificar la cantidad de combustible que tenía el tanque antes de esta primera carga."
                ) % ticket.vehicle_id.name)
    
    @api.constrains('initial_fuel_manual', 'vehicle_tank_capacity')
    def _check_initial_fuel_capacity(self):
        """Validar que el combustible inicial no exceda la capacidad del tanque"""
        for ticket in self:
            if (ticket.initial_fuel_manual > 0 and 
                ticket.vehicle_tank_capacity > 0 and 
                ticket.initial_fuel_manual > ticket.vehicle_tank_capacity):
                raise ValidationError(_(
                    "El combustible inicial (%.2f L) no puede ser mayor que la capacidad del tanque (%.2f L) del vehículo '%s'."
                ) % (ticket.initial_fuel_manual, ticket.vehicle_tank_capacity, ticket.vehicle_id.name))
    
    @api.constrains('card_id', 'date', 'day_sequence')
    def _check_day_sequence_unique(self):
        """
        Validar que no haya secuencias duplicadas para la misma tarjeta y fecha
        """
        for ticket in self:
            if ticket.card_id and ticket.date:
                duplicate = self.env['fuel.ticket'].search([
                    ('card_id', '=', ticket.card_id.id),
                    ('date', '=', ticket.date),
                    ('day_sequence', '=', ticket.day_sequence),
                    ('id', '!=', ticket.id),
                ], limit=1)
                
                if duplicate:
                    raise ValidationError(_(
                        "Ya existe un ticket con la secuencia %s para la tarjeta '%s' en la fecha %s. "
                        "Esto puede indicar un problema en el orden de procesamiento."
                    ) % (ticket.day_sequence, ticket.card_id.name, ticket.date))
    
    def action_confirm(self):
        """
        CORREGIDO: Confirmar tickets en orden correcto dentro del mismo día
        """
        # Ordenar tickets por fecha y secuencia del día
        sorted_tickets = self.sorted(lambda t: (t.date, t.day_sequence))
        
        for ticket in sorted_tickets:
            if ticket.state == 'draft':
                # Recalcular saldo inicial por si otros tickets del día fueron confirmados antes
                if ticket.day_sequence > 1:
                    new_initial_balance = ticket._get_initial_balance_for_card(
                        ticket.card_id, 
                        ticket.date
                    )
                    if new_initial_balance != ticket.initial_balance:
                        ticket.write({'initial_balance': new_initial_balance})
                        _logger.info(f"Updated initial balance for ticket {ticket.id} from {ticket.initial_balance} to {new_initial_balance}")
                
                # Verificar saldo suficiente
                if ticket.amount > ticket.initial_balance:
                    raise ValidationError(_(
                        "La tarjeta no tiene saldo suficiente para el ticket %s. "
                        "Saldo disponible: %.2f, Importe requerido: %.2f"
                    ) % (ticket.name, ticket.initial_balance, ticket.amount))
                
                # Actualizar saldo de la tarjeta
                ticket.card_id.write({'current_balance': ticket.final_balance})
                
                # Actualizar odómetro del vehículo si aplica
                if ticket.vehicle_id and ticket.odometer > 0:
                    # Crear registro de odómetro
                    self.env['fleet.vehicle.odometer'].create({
                        'vehicle_id': ticket.vehicle_id.id,
                        'value': ticket.odometer,
                        'date': ticket.date,
                    })
                    
                    # Actualizar odómetro del vehículo
                    ticket.vehicle_id.write({'odometer': ticket.odometer})
                
                ticket.state = 'confirmed'
                _logger.info(f"Ticket {ticket.id} confirmed. Final balance: {ticket.final_balance}")
    
    def action_cancel(self):
        for ticket in self:
            if ticket.state == 'confirmed':
                # Restaurar saldo de la tarjeta
                ticket.card_id.write({'current_balance': ticket.card_id.current_balance + ticket.amount})
                ticket.state = 'cancelled'
            elif ticket.state == 'draft':
                ticket.state = 'cancelled'
    
    def action_reset_to_draft(self):
        for ticket in self:
            if ticket.state == 'cancelled':
                ticket.state = 'draft'
    
    def get_fuel_summary(self):
        self.ensure_one()
        if self.card_type != 'vehicle' or not self.vehicle_id:
            return {}
        
        return {
            'vehicle_name': self.vehicle_id.name,
            'tank_capacity': self.vehicle_tank_capacity,
            'fuel_consumed': self.fuel_consumed,
            'remaining_before': self.remaining_fuel_before,
            'liters_added': self.liters,
            'fuel_after_fill': self.fuel_after_fill,
            'capacity_exceeded': self.tank_capacity_exceeded,
            'excess_fuel': max(0, self.fuel_after_fill - self.vehicle_tank_capacity),
            'fill_type': self.tank_fill_type,
            'distance_traveled': self.distance_traveled,
            'fuel_efficiency': self.fuel_efficiency,
        }
