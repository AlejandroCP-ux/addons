# -*- coding: utf-8 -*-
from odoo import models, fields

class ITAssetBacklog(models.Model):
    _inherit = 'it.asset.backlog'

    software_ids = fields.Many2many(
        'it.asset.software',
        'backlog_software_rel',
        'backlog_id',
        'software_id',
        string='Software Detectado'
    )