# -*- coding: utf-8 -*-
import time
import calendar

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class CalendarWorksectionSection(models.Model):
    _name = 'calendar_workplan.section'
    _description = 'Work Plan Section'
    _parent_store = True
    _order = 'parent_id, sequence'

    name = fields.Char("Section Name", required=True)
    parent_id = fields.Many2one('calendar_workplan.section', string='Parent Section', index=True, domain="[('id', '!=', id)]", ondelete="restrict")
    child_ids = fields.One2many('calendar_workplan.section', 'parent_id', string='Child Sections')
    parent_path = fields.Char(index=True, unaccent=False)
    active = fields.Boolean(default=True)
    sequence = fields.Integer()
    workplan_ids = fields.Many2many('calendar_workplan.plan', string="Plans", domain="[('scope', '=', 'annual')]")
