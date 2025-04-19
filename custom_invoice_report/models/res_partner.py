# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    asi_contract = fields.Char('Contract')