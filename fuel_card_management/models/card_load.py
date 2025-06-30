# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelCardLoad(models.Model):
    _name = 'fuel.card.load'
    _description = 'Carga de Tarjeta de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True, tracking=True,
                             domain="[('state', 'in', ['available', 'assigned'])]")

    carrier_id = fields.Many2one(related='card_id.carrier_id', string='Portador', readonly=True, store=True)                         
    
    initial_balance = fields.Float(string='Saldo Inicial', readonly=True, tracking=True)
    amount = fields.Float(string='Importe', required=True, tracking=True)
    final_balance = fields.Float(string='Saldo Final', compute='_compute_final_balance', store=True, tracking=True)
    
    unassigned_id = fields.Many2one('fuel.unassigned', string='Combustible No Asignado', tracking=True,
                                   domain="[('state', '=', 'confirmed'), ('carrier_id', '=', carrier_id)]")
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    notes = fields.Text(string='Notas')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.card.load') or _('Nuevo')
        
        # Obtener saldo inicial de la tarjeta
        if vals.get('card_id'):
            card = self.env['fuel.magnetic.card'].browse(vals['card_id'])
            vals['initial_balance'] = card.current_balance
        
        return super(FuelCardLoad, self).create(vals)
    
    @api.depends('initial_balance', 'amount')
    def _compute_final_balance(self):
        for load in self:
            load.final_balance = load.initial_balance + load.amount
    
    @api.onchange('card_id')
    def _onchange_card_id(self):
        if self.card_id:
            self.initial_balance = self.card_id.current_balance
            # Limpiar el campo unassigned_id para aplicar el nuevo dominio
            self.unassigned_id = False
            
            return {
                'domain': {
                    'unassigned_id': [('state', '=', 'confirmed'), ('carrier_id', '=', self.card_id.carrier_id.id if self.card_id.carrier_id else False)]
                }
            }
    
    @api.onchange('unassigned_id')
    def _onchange_unassigned_id(self):
        if self.unassigned_id:
            self.amount = self.unassigned_id.amount
    
    def action_confirm(self):
        for load in self:
            if load.state == 'draft':
                # Verificar que la tarjeta tenga un portador de combustible asignado
                if not load.card_id.carrier_id:
                    raise ValidationError(_("La tarjeta seleccionada no tiene un portador de combustible asignado."))
                
                # Verificar si hay suficiente combustible no asignado
                if load.unassigned_id and load.amount > load.unassigned_id.amount:
                    raise ValidationError(_("No puede cargar más combustible del disponible en el registro no asignado."))
                
                # Verificar que el portador coincida
                if load.unassigned_id and load.carrier_id != load.unassigned_id.carrier_id:
                    raise ValidationError(_("El portador de combustible de la tarjeta debe coincidir con el del combustible no asignado."))
                
                # Actualizar saldo de la tarjeta
                load.card_id.write({'current_balance': load.final_balance})
                
                # Actualizar registro de combustible no asignado si aplica
                if load.unassigned_id:
                    # Si se usa todo el combustible no asignado, se marca como cancelado
                    if load.amount == load.unassigned_id.amount:
                        load.unassigned_id.write({'state': 'cancelled'})
                    # Si se usa parcialmente, se crea un nuevo registro con la diferencia
                    elif load.amount < load.unassigned_id.amount:
                        remaining = load.unassigned_id.amount - load.amount
                     
                        self.env['fuel.unassigned'].with_context(from_invoice_confirmation=True).create({
                            'supplier_id': load.unassigned_id.supplier_id.id,
                            'invoice_id': load.unassigned_id.invoice_id.id,
                            'carrier_id': load.unassigned_id.carrier_id.id, 
                            'date': fields.Date.today(),
                            'amount': remaining,
                            'unit_price': load.unassigned_id.unit_price,
                            'state': 'confirmed',
                        })
                        load.unassigned_id.write({'state': 'cancelled'})
                
                load.state = 'confirmed'
    
    def action_cancel(self):
        for load in self:
            if load.state == 'confirmed':
                # Verificar si la tarjeta tiene suficiente saldo para revertir la carga
                if load.card_id.current_balance < load.amount:
                    raise ValidationError(_("No se puede cancelar la carga porque la tarjeta no tiene suficiente saldo."))
                
                # Revertir saldo de la tarjeta
                load.card_id.write({'current_balance': load.card_id.current_balance - load.amount})
                
                # Restaurar combustible no asignado si aplica
                if load.unassigned_id:
                    load.unassigned_id.write({'state': 'confirmed'})
                
                load.state = 'cancelled'
            elif load.state == 'draft':
                load.state = 'cancelled'
    
    def action_reset_to_draft(self):
        for load in self:
            if load.state == 'cancelled':
                load.state = 'draft'
