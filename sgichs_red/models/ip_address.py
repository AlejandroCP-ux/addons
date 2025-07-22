# -*- coding: utf-8 -*-
from odoo import models, fields, api

class IPAddress(models.Model):
    _name = 'it.ip.address'
    _description = 'Dirección IP'
    _order = 'address'

    address = fields.Char(string='Dirección IP', required=True, unique=True)
    description = fields.Char(string='Descripción')

    hardware_ids = fields.Many2many(
        'it.asset.hardware',
        'hardware_ip_rel',
        'ip_id',
        'hardware_id',
        string='Hardware Asignado'
    )
    hardware_count = fields.Integer(
        string='Nº de Dispositivos',
        compute='_compute_hardware_count'
    )

    def _compute_hardware_count(self):
        for ip in self:
            ip.hardware_count = len(ip.hardware_ids)