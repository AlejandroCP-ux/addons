# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class FuelSupplier(models.Model):
    _name = 'fuel.supplier'
    _description = 'Proveedor de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Nombre', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Contacto', required=True, tracking=True)
    
    card_type = fields.Selection([
        ('physical', 'Tarjeta Física'),
        ('virtual', 'Tarjeta Virtual'),
        ('both', 'Ambas')
    ], string='Tipo de Tarjeta', default='physical', required=True, tracking=True)
    
    contract_number = fields.Char(string='Número de Contrato', tracking=True)
    contract_start_date = fields.Date(string='Fecha de Inicio de Contrato', tracking=True)
    contract_end_date = fields.Date(string='Fecha de Fin de Contrato', tracking=True)
    
    card_ids = fields.One2many('fuel.magnetic.card', 'supplier_id', string='Tarjetas')
    card_count = fields.Integer(compute='_compute_card_count', string='Número de Tarjetas')
    
    invoice_ids = fields.One2many('fuel.invoice', 'supplier_id', string='Facturas')
    invoice_count = fields.Integer(compute='_compute_invoice_count', string='Número de Facturas')
    
    notes = fields.Text(string='Notas')
    
    _sql_constraints = [
        ('partner_uniq', 'unique(partner_id)', 'Ya existe un proveedor para este contacto!')
    ]
    
    @api.depends('card_ids')
    def _compute_card_count(self):
        for supplier in self:
            supplier.card_count = len(supplier.card_ids)
    
    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for supplier in self:
            supplier.invoice_count = len(supplier.invoice_ids)