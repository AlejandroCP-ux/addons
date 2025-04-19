# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class Employee(models.Model):
    _inherit = "hr.employee"

    default_evaluation_template_id = fields.Many2one("performance.evaluation.program.config", tracking=1)
   
    