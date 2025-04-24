# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CalendarWorkplanPlan(models.Model):
    _inherit = 'calendar_workplan.plan'
    
    qualitative_analysis = fields.Text("Análisis cualitativo")

    def action_generate_evaluation(self):
        for record in self:
           record.qualitative_analysis = self.env['calendar_workplan.evaluation'].generate_evaluation(self.id)
        return True