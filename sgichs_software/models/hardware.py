# -*- coding: utf-8 -*-
from odoo import models, fields

class Hardware(models.Model):
    _inherit = 'it.asset.hardware'

    software_ids = fields.Many2many(
        'it.asset.software',
        'hardware_software_rel',
        'hardware_id',
        'software_id',
        string='Software Instalado'
    )