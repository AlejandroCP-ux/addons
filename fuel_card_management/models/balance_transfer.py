# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelBalanceTransfer(models.Model):
    _name = 'fuel.balance.transfer'
    _description = 'Traspaso de Saldo entre Tarjetas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    source_card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta Origen', required=True, tracking=True,
                                    domain="[('state', 'in', ['available', 'assigned']), ('current_balance', '>', 0)]")
    target_card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta Destino', required=True, tracking=True,
                                    domain="[('state', 'in', ['available', 'assigned']), ('id', '!=', source_card_id)]")
    
    source_initial_balance = fields.Float(string='Saldo Inicial Origen', readonly=True, tracking=True)
    target_initial_balance = fields.Float(string='Saldo Inicial Destino', readonly=True, tracking=True)
    
    amount = fields.Float(string='Importe', required=True, tracking=True)
    
    source_final_balance = fields.Float(string='Saldo Final Origen', compute='_compute_final_balances', store=True, tracking=True)
    target_final_balance = fields.Float(string='Saldo Final Destino', compute='_compute_final_balances', store=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    notes = fields.Text(string='Notas')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.balance.transfer') or _('Nuevo')
        
        # Obtener saldos iniciales
        if vals.get('source_card_id'):
            source_card = self.env['fuel.magnetic.card'].browse(vals['source_card_id'])
            vals['source_initial_balance'] = source_card.current_balance
        
        if vals.get('target_card_id'):
            target_card = self.env['fuel.magnetic.card'].browse(vals['target_card_id'])
            vals['target_initial_balance'] = target_card.current_balance
        
        return super(FuelBalanceTransfer, self).create(vals)
    
    @api.depends('source_initial_balance', 'target_initial_balance', 'amount')
    def _compute_final_balances(self):
        for transfer in self:
            transfer.source_final_balance = transfer.source_initial_balance - transfer.amount
            transfer.target_final_balance = transfer.target_initial_balance + transfer.amount
    
    @api.onchange('source_card_id')
    def _onchange_source_card_id(self):
        if self.source_card_id:
            self.source_initial_balance = self.source_card_id.current_balance
    
    @api.onchange('target_card_id')
    def _onchange_target_card_id(self):
        if self.target_card_id:
            self.target_initial_balance = self.target_card_id.current_balance
    
    @api.constrains('amount', 'source_initial_balance')
    def _check_amount(self):
        for transfer in self:
            if transfer.amount <= 0:
                raise ValidationError(_("El importe debe ser mayor que cero."))
            if transfer.amount > transfer.source_initial_balance:
                raise ValidationError(_("No puede transferir más del saldo disponible en la tarjeta origen."))
    
    @api.constrains('source_card_id', 'target_card_id')
    def _check_cards(self):
        for transfer in self:
            if transfer.source_card_id == transfer.target_card_id:
                raise ValidationError(_("Las tarjetas origen y destino deben ser diferentes."))
    
    def action_confirm(self):
        for transfer in self:
            if transfer.state == 'draft':
                # Verificar saldo suficiente
                if transfer.amount > transfer.source_card_id.current_balance:
                    raise ValidationError(_("La tarjeta origen no tiene saldo suficiente para esta transferencia."))
                
                # Actualizar saldos de las tarjetas
                transfer.source_card_id.write({'current_balance': transfer.source_final_balance})
                transfer.target_card_id.write({'current_balance': transfer.target_final_balance})
                
                transfer.state = 'confirmed'
    
    def action_cancel(self):
        for transfer in self:
            if transfer.state == 'confirmed':
                # Restaurar saldos de las tarjetas
                transfer.source_card_id.write({'current_balance': transfer.source_initial_balance})
                transfer.target_card_id.write({'current_balance': transfer.target_initial_balance})
                
                transfer.state = 'cancelled'
            elif transfer.state == 'draft':
                transfer.state = 'cancelled'
    
    def action_reset_to_draft(self):
        for transfer in self:
            if transfer.state == 'cancelled':
                transfer.state = 'draft'