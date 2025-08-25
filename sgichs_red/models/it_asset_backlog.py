# -*- coding: utf-8 -*-
from odoo import models, fields

class ITAssetBacklog(models.Model):
    _inherit = 'it.asset.backlog'

    ip_ids = fields.Many2many(
        'it.ip.address',
        'backlog_ip_rel',
        'backlog_id',
        'ip_id',
        string='IPs Detectadas'
    )