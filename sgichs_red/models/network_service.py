# -*- coding: utf-8 -*-
from odoo import models, fields

class NetworkService(models.Model):
    _name = 'it.asset.network_service'
    _description = 'Servicio de Red'
    _inherit = 'it.asset'

    type = fields.Selection(
        selection_add=[('network_service', 'Servicio de Red')],
        ondelete={'network_service': 'cascade'}
    )
    ip_address = fields.Char(string='Dirección IP / Endpoint', required=True)
    port = fields.Integer(string='Puerto')
    protocol = fields.Selection([
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('icmp', 'ICMP'),
        ('other', 'Otro')
    ], string='Protocolo')