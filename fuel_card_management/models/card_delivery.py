# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelCardDelivery(models.Model):
    _name = 'fuel.card.delivery'
    _description = 'Entrega/Devolución de Tarjeta de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True, tracking=True)
    
    delivery_type = fields.Selection([
        ('delivery', 'Entrega'),
        ('return', 'Devolución')
    ], string='Tipo', required=True, default='delivery', tracking=True)
    
    holder_id = fields.Many2one('fuel.card.holder', string='Titular', tracking=True)
    driver_id = fields.Many2one('fuel.driver', string='Conductor', tracking=True)
    
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', tracking=True)
    generator_id = fields.Many2one('fuel.power.generator', string='Generador', tracking=True)
    
    balance = fields.Float(string='Saldo Actual', related='card_id.current_balance', readonly=True)
    
    # Campos relacionados para mostrar información de la tarjeta
    card_type = fields.Selection(related='card_id.card_type', string='Tipo de Tarjeta', readonly=True)
    card_supplier_id = fields.Many2one(related='card_id.supplier_id', string='Proveedor', readonly=True)
    card_operational_state = fields.Selection(related='card_id.operational_state', string='Estado Operativo', readonly=True)
    card_expiry_date = fields.Date(related='card_id.expiry_date', string='Fecha de Vencimiento', readonly=True)
    card_carrier_id = fields.Many2one(related='card_id.carrier_id', string='Portador de la Tarjeta', readonly=True)
    
    # Campos para mostrar asignación actual (para devoluciones)
    card_current_holder_id = fields.Many2one(related='card_id.holder_id', string='Titular Actual', readonly=True)
    card_current_driver_id = fields.Many2one(related='card_id.driver_id', string='Conductor Actual', readonly=True)
    card_current_vehicle_id = fields.Many2one(related='card_id.vehicle_id', string='Vehículo Actual', readonly=True)
    card_current_generator_id = fields.Many2one(related='card_id.generator_id', string='Generador Actual', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    notes = fields.Text(string='Notas')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.card.delivery') or _('Nuevo')
        return super(FuelCardDelivery, self).create(vals)
    
    @api.onchange('card_id')
    def _onchange_card_id(self):
        if self.card_id:
            # Si es devolución, llenar con los datos actuales de la tarjeta
            if self.delivery_type == 'return':
                self.holder_id = self.card_id.holder_id
                self.driver_id = self.card_id.driver_id
                self.vehicle_id = self.card_id.vehicle_id
                self.generator_id = self.card_id.generator_id
            else:
                # Si es entrega, limpiar los campos para permitir asignación nueva
                self.holder_id = False
                self.driver_id = False
                self.vehicle_id = False
                self.generator_id = False
    
    @api.onchange('delivery_type')
    def _onchange_delivery_type(self):
        # Limpiar la tarjeta seleccionada al cambiar el tipo
        self.card_id = False
        self.holder_id = False
        self.driver_id = False
        self.vehicle_id = False
        self.generator_id = False
        
        if self.delivery_type == 'delivery':
            # Para entrega, mostrar solo tarjetas disponibles
            return {'domain': {'card_id': [('operational_state', '=', 'available'), ('active', '=', True)]}}
        else:
            # Para devolución, mostrar solo tarjetas asignadas
            return {'domain': {'card_id': [('operational_state', '=', 'assigned'), ('active', '=', True)]}}
    
    @api.onchange('card_type')
    def _onchange_card_type(self):
        """Limpiar campos incompatibles al cambiar el tipo de tarjeta"""
        if self.card_type == 'vehicle':
            self.generator_id = False
        elif self.card_type == 'generator':
            self.vehicle_id = False
    
    @api.constrains('card_id', 'delivery_type')
    def _check_card_state(self):
        for delivery in self:
            if delivery.card_id:
                if delivery.delivery_type == 'delivery' and not delivery.card_id.can_be_delivered():
                    raise ValidationError(_("Solo puede entregar tarjetas que estén disponibles."))
                elif delivery.delivery_type == 'return' and not delivery.card_id.can_be_returned():
                    raise ValidationError(_("Solo puede recibir tarjetas que estén asignadas."))
    
    @api.constrains('card_id', 'vehicle_id', 'delivery_type')
    def _check_carrier_compatibility(self):
        """Validar que el portador de la tarjeta coincida con el del vehículo"""
        for delivery in self:
            if (delivery.delivery_type == 'delivery' and 
                delivery.card_id and 
                delivery.vehicle_id and 
                delivery.card_id.carrier_id and 
                delivery.vehicle_id.fuel_type):
                
                if delivery.card_id.carrier_id != delivery.vehicle_id.fuel_type:
                    raise ValidationError(_(
                        "El portador de combustible de la tarjeta (%s) no coincide con el del vehículo (%s).\n"
                        "La tarjeta debe ser del mismo tipo de combustible que el vehículo."
                    ) % (delivery.card_id.carrier_id.name, delivery.vehicle_id.fuel_type.name))
    
    @api.constrains('card_type', 'vehicle_id', 'generator_id', 'delivery_type')
    def _check_card_type_assignment(self):
        """Validar que la asignación sea compatible con el tipo de tarjeta"""
        for delivery in self:
            if delivery.delivery_type == 'delivery' and delivery.card_id:
                card_type = delivery.card_type
                
                # Validaciones específicas por tipo de tarjeta
                if card_type == 'vehicle':
                    if delivery.generator_id:
                        raise ValidationError(_("Las tarjetas de vehículo no pueden asignarse a generadores."))
                    if not delivery.vehicle_id:
                        raise ValidationError(_("Las tarjetas de vehículo requieren un vehículo asignado."))
                
                elif card_type == 'generator':
                    if delivery.vehicle_id:
                        raise ValidationError(_("Las tarjetas de generador no pueden asignarse a vehículos."))
                    if not delivery.generator_id:
                        raise ValidationError(_("Las tarjetas de generador requieren un generador asignado."))
                
                elif card_type == 'other':
                    # Las tarjetas tipo 'other' pueden asignarse a cualquiera, pero solo a uno
                    if delivery.vehicle_id and delivery.generator_id:
                        raise ValidationError(_("Una tarjeta no puede asignarse simultáneamente a un vehículo y un generador."))
                    if not delivery.vehicle_id and not delivery.generator_id:
                        raise ValidationError(_("Debe asignar la tarjeta a un vehículo o generador."))
    
    @api.constrains('holder_id', 'delivery_type')
    def _check_holder_required(self):
        """Validar que el titular sea obligatorio para entregas"""
        for delivery in self:
            if delivery.delivery_type == 'delivery' and not delivery.holder_id:
                raise ValidationError(_("El titular es obligatorio para las entregas de tarjetas."))
    
    @api.constrains('vehicle_id', 'generator_id', 'delivery_type', 'state')
    def _check_unique_assignment(self):
        """Validar que un vehículo o generador solo tenga una tarjeta asignada"""
        for delivery in self:
            if delivery.delivery_type == 'delivery' and delivery.state in ['draft', 'confirmed']:
                
                # Validar asignación única para vehículos
                if delivery.vehicle_id:
                    # Buscar otras tarjetas asignadas al mismo vehículo
                    existing_cards = self.env['fuel.magnetic.card'].search([
                        ('vehicle_id', '=', delivery.vehicle_id.id),
                        ('operational_state', '=', 'assigned'),
                        ('active', '=', True),
                        ('id', '!=', delivery.card_id.id)  # Excluir la tarjeta actual
                    ])
                    
                    if existing_cards:
                        card_names = ', '.join(existing_cards.mapped('name'))
                        raise ValidationError(_(
                            "El vehículo '%s' ya tiene asignada(s) la(s) tarjeta(s): %s.\n"
                            "Un vehículo solo puede tener una tarjeta asignada a la vez."
                        ) % (delivery.vehicle_id.name, card_names))
                
                # Validar asignación única para generadores
                if delivery.generator_id:
                    # Buscar otras tarjetas asignadas al mismo generador
                    existing_cards = self.env['fuel.magnetic.card'].search([
                        ('generator_id', '=', delivery.generator_id.id),
                        ('operational_state', '=', 'assigned'),
                        ('active', '=', True),
                        ('id', '!=', delivery.card_id.id)  # Excluir la tarjeta actual
                    ])
                    
                    if existing_cards:
                        card_names = ', '.join(existing_cards.mapped('name'))
                        raise ValidationError(_(
                            "El generador '%s' ya tiene asignada(s) la(s) tarjeta(s): %s.\n"
                            "Un generador solo puede tener una tarjeta asignada a la vez."
                        ) % (delivery.generator_id.name, card_names))
    
    def _validate_delivery_requirements(self):
        """Validar todos los requisitos antes de confirmar una entrega"""
        self.ensure_one()
        
        if self.delivery_type == 'delivery':
            # Validar titular obligatorio
            if not self.holder_id:
                raise ValidationError(_("El titular es obligatorio para las entregas."))
            
            # Validar asignación según tipo de tarjeta
            if self.card_type == 'vehicle' and not self.vehicle_id:
                raise ValidationError(_("Debe asignar un vehículo para tarjetas de tipo vehículo."))
            elif self.card_type == 'generator' and not self.generator_id:
                raise ValidationError(_("Debe asignar un generador para tarjetas de tipo generador."))
            elif self.card_type == 'other' and not self.vehicle_id and not self.generator_id:
                raise ValidationError(_("Debe asignar un vehículo o generador para esta tarjeta."))
    
    def action_confirm(self):
        for delivery in self:
            if delivery.state == 'draft':
                # Validar requisitos antes de confirmar
                delivery._validate_delivery_requirements()
                
                if delivery.delivery_type == 'delivery':
                    # Verificar que la tarjeta esté disponible
                    if not delivery.card_id.can_be_delivered():
                        raise ValidationError(_("Solo puede entregar tarjetas que estén disponibles."))
                    
                    # Verificación final de asignación única justo antes de confirmar
                    if delivery.vehicle_id:
                        existing_cards = self.env['fuel.magnetic.card'].search([
                            ('vehicle_id', '=', delivery.vehicle_id.id),
                            ('operational_state', '=', 'assigned'),
                            ('active', '=', True)
                        ])
                        if existing_cards:
                            card_names = ', '.join(existing_cards.mapped('name'))
                            raise ValidationError(_(
                                "No se puede confirmar la entrega. El vehículo '%s' ya tiene asignada(s) "
                                "la(s) tarjeta(s): %s.\nPrimero debe devolver la(s) tarjeta(s) existente(s)."
                            ) % (delivery.vehicle_id.name, card_names))
                    
                    if delivery.generator_id:
                        existing_cards = self.env['fuel.magnetic.card'].search([
                            ('generator_id', '=', delivery.generator_id.id),
                            ('operational_state', '=', 'assigned'),
                            ('active', '=', True)
                        ])
                        if existing_cards:
                            card_names = ', '.join(existing_cards.mapped('name'))
                            raise ValidationError(_(
                                "No se puede confirmar la entrega. El generador '%s' ya tiene asignada(s) "
                                "la(s) tarjeta(s): %s.\nPrimero debe devolver la(s) tarjeta(s) existente(s)."
                            ) % (delivery.generator_id.name, card_names))
                    
                    # Entregar tarjeta
                    delivery.card_id._set_delivered(
                        holder_id=delivery.holder_id.id if delivery.holder_id else False,
                        driver_id=delivery.driver_id.id if delivery.driver_id else False,
                        vehicle_id=delivery.vehicle_id.id if delivery.vehicle_id else False,
                        generator_id=delivery.generator_id.id if delivery.generator_id else False
                    )
                    
                    # Mensaje de seguimiento
                    delivery.card_id.message_post(
                        body=_("Tarjeta entregada mediante: %s") % delivery.name,
                        message_type='notification'
                    )
                    
                else: 
                    # Verificar que la tarjeta esté asignada
                    if not delivery.card_id.can_be_returned():
                        raise ValidationError(_("Solo puede recibir tarjetas que estén asignadas."))
                    
                    # Devolver tarjeta
                    delivery.card_id._set_returned()
                    
                    # Mensaje de seguimiento
                    delivery.card_id.message_post(
                        body=_("Tarjeta devuelta mediante: %s") % delivery.name,
                        message_type='notification'
                    )
                
                delivery.state = 'confirmed'
                
                # Mensaje en el registro de entrega
                delivery.message_post(
                    body=_("Proceso de %s confirmado para la tarjeta %s") % (
                        'entrega' if delivery.delivery_type == 'delivery' else 'devolución',
                        delivery.card_id.name
                    ),
                    message_type='notification'
                )
    
    def action_cancel(self):
        for delivery in self:
            if delivery.state == 'confirmed':
                # Revertir cambios en la tarjeta
                if delivery.delivery_type == 'delivery':
                    # Si fue una entrega, devolver la tarjeta a disponible
                    delivery.card_id._set_returned()
                    
                    # Mensaje de seguimiento
                    delivery.card_id.message_post(
                        body=_("Entrega cancelada, tarjeta devuelta a disponible: %s") % delivery.name,
                        message_type='notification'
                    )
                    
                else:  
                    # Si fue una devolución, volver a asignar la tarjeta
                    delivery.card_id._set_delivered(
                        holder_id=delivery.holder_id.id if delivery.holder_id else False,
                        driver_id=delivery.driver_id.id if delivery.driver_id else False,
                        vehicle_id=delivery.vehicle_id.id if delivery.vehicle_id else False,
                        generator_id=delivery.generator_id.id if delivery.generator_id else False
                    )
                    
                    # Mensaje de seguimiento
                    delivery.card_id.message_post(
                        body=_("Devolución cancelada, tarjeta vuelve a estar asignada: %s") % delivery.name,
                        message_type='notification'
                    )
                
                delivery.state = 'cancelled'
            elif delivery.state == 'draft':
                delivery.state = 'cancelled'
            
            # Mensaje en el registro de entrega
            delivery.message_post(
                body=_("Proceso de %s cancelado") % (
                    'entrega' if delivery.delivery_type == 'delivery' else 'devolución'
                ),
                message_type='notification'
            )
    
    def action_reset_to_draft(self):
        for delivery in self:
            if delivery.state == 'cancelled':
                delivery.state = 'draft'
                
                # Mensaje en el registro de entrega
                delivery.message_post(
                    body=_("Proceso devuelto a borrador"),
                    message_type='notification'
                )
    
    def name_get(self):
        """Personalizar la representación del nombre"""
        result = []
        for delivery in self:
            name = delivery.name
            if delivery.card_id:
                operation = _('Entrega') if delivery.delivery_type == 'delivery' else _('Devolución')
                name = f"{name} - {operation} {delivery.card_id.name}"
            result.append((delivery.id, name))
        return result
