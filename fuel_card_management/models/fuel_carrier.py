# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelCarrier(models.Model):
    _name = 'fuel.carrier'
    _description = 'Portador de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, tracking=True, 
                       help="Nombre del portador de combustible (ej. Diesel, Gasolina)")

    current_price = fields.Float(string='Precio Actual por Litro', required=True, tracking=True,
                               help="Precio actual por litro del portador de combustible")

    description = fields.Text(string='Descripción',
                             help="Descripción adicional del portador de combustible")

    active = fields.Boolean(string='Activo', default=True, tracking=True,
                           help="Si está desactivado, este portador no será visible")

    price_history_ids = fields.One2many('fuel.carrier.price.history', 'carrier_id', 
                                       string='Historial de Precios')

    card_count = fields.Integer(string='Tarjetas', compute='_compute_card_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El nombre del portador de combustible debe ser único!')
    ]

    @api.constrains('current_price')
    def _check_current_price(self):
        for carrier in self:
            if carrier.current_price <= 0:
                raise ValidationError(_("El precio por litro debe ser mayor que cero."))

    def _compute_card_count(self):
        for carrier in self:
            carrier.card_count = self.env['fuel.magnetic.card'].search_count([
                ('carrier_id', '=', carrier.id)
            ])

    def action_view_cards(self):
        self.ensure_one()
        return {
            'name': _('Tarjetas'),
            'type': 'ir.actions.act_window',
            'res_model': 'fuel.magnetic.card',
            'view_mode': 'tree,form',
            'domain': [('carrier_id', '=', self.id)],
            'context': {'default_carrier_id': self.id},
        }

    def write(self, vals):
        if 'current_price' in vals and vals['current_price'] != self.current_price:
            self.env['fuel.carrier.price.history'].create({
                'carrier_id': self.id,
                'price': vals['current_price'],
                'date': fields.Date.today(),
            })
        return super(FuelCarrier, self).write(vals)

class FuelCarrierPriceHistory(models.Model):
    _name = 'fuel.carrier.price.history'
    _description = 'Historial de Precios de Portador de Combustible'
    _order = 'date desc, id desc'

    carrier_id = fields.Many2one('fuel.carrier', string='Portador', required=True, ondelete='cascade')
    price = fields.Float(string='Precio por Litro', required=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    notes = fields.Text(string='Notas')
