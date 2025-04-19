from odoo import models, fields


class Challenge(models.Model):
    _inherit = 'gamification.challenge'

    active = fields.Boolean("Active", default=True)
