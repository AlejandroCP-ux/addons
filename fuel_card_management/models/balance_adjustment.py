# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelBalanceAdjustment(models.Model):
    _name = 'fuel.balance.adjustment'
    _description = 'Ajuste de Saldo de Tarjeta'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True, tracking=True,
                             domain="[('state', 'in', ['available', 'assigned'])]")
    
    adjustment_type = fields.Selection([
        ('increase', 'Incremento'),
        ('decrease', 'Decremento')
    ], string='Tipo de Ajuste', required=True, default='increase', tracking=True)
    
    initial_balance = fields.Float(string='Saldo Inicial', readonly=True, tracking=True)
    amount = fields.Float(string='Importe', required=True, tracking=True)
    final_balance = fields.Float(string='Saldo Final', compute='_compute_final_balance', store=True, tracking=True)
    
    reason = fields.Selection([
        ('error', 'Error de Registro'),
        ('loss', 'Pérdida'),
        ('theft', 'Robo'),
        ('other', 'Otro')
    ], string='Motivo', required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    notes = fields.Text(string='Notas')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.balance.adjustment') or _('Nuevo')
        
        # Obtener saldo inicial de la tarjeta
        if vals.get('card_id'):
            card = self.env['fuel.magnetic.card'].browse(vals['card_id'])
            vals['initial_balance'] = card.current_balance
        
        return super(FuelBalanceAdjustment, self).create(vals)
    
    @api.depends('initial_balance', 'amount', 'adjustment_type')
    def _compute_final_balance(self):
        for adjustment in self:
            if adjustment.adjustment_type == 'increase':
                adjustment.final_balance = adjustment.initial_balance + adjustment.amount
            else:
                adjustment.final_balance = adjustment.initial_balance - adjustment.amount
    
    @api.onchange('card_id')
    def _onchange_card_id(self):
        if self.card_id:
            self.initial_balance = self.card_id.current_balance
    
    @api.constrains('amount', 'adjustment_type', 'initial_balance')
    def _check_amount(self):
        for adjustment in self:
            if adjustment.adjustment_type == 'decrease' and adjustment.amount > adjustment.initial_balance:
                raise ValidationError(_("No puede decrementar más del saldo disponible en la tarjeta."))
    
    def action_confirm(self):
        for adjustment in self:
            if adjustment.state == 'draft':
                # Verificar saldo suficiente para decrementos
                if adjustment.adjustment_type == 'decrease' and adjustment.amount > adjustment.card_id.current_balance:
                    raise ValidationError(_("La tarjeta no tiene saldo suficiente para este ajuste."))
                
                # Actualizar saldo de la tarjeta
                adjustment.card_id.write({'current_balance': adjustment.final_balance})
                
                adjustment.state = 'confirmed'
    
    def action_cancel(self):
        for adjustment in self:
            if adjustment.state == 'confirmed':
                # Restaurar saldo de la tarjeta
                if adjustment.adjustment_type == 'increase':
                    adjustment.card_id.write({'current_balance': adjustment.card_id.current_balance - adjustment.amount})
                else:
                    adjustment.card_id.write({'current_balance': adjustment.card_id.current_balance + adjustment.amount})
                
                adjustment.state = 'cancelled'
            elif adjustment.state == 'draft':
                adjustment.state = 'cancelled'
    
    def action_reset_to_draft(self):
        for adjustment in self:
            if adjustment.state == 'cancelled':
                adjustment.state = 'draft'