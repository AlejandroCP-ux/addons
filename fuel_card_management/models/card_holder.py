# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class FuelCardHolder(models.Model):
    _name = 'fuel.card.holder'
    _description = 'Titular de Tarjeta de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Nombre', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Contacto', required=True, tracking=True)
    identification = fields.Char(string='Identificación', tracking=True)
    position = fields.Char(string='Cargo', tracking=True)
    department = fields.Char(string='Departamento', tracking=True)
    
    card_ids = fields.One2many('fuel.magnetic.card', 'holder_id', string='Tarjetas Asignadas')
    card_count = fields.Integer(compute='_compute_card_count', string='Número de Tarjetas')
    
    notes = fields.Text(string='Notas')
    
    _sql_constraints = [
        ('partner_uniq', 'unique(partner_id)', 'Ya existe un titular para este contacto!')
    ]
    
    @api.depends('card_ids')
    def _compute_card_count(self):
        for holder in self:
            holder.card_count = len(holder.card_ids)