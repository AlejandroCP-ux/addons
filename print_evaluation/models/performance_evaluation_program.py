from odoo import models, fields, api

class PerformanceEvaluationProgramInherit(models.Model):
    _inherit = 'performance.evaluation.program'

    overall_score_category = fields.Char(
        string="Categoría de Puntuación",
        compute='_compute_overall_score_category',
        store=True 
    )

    @api.depends('overall_score')
    def _compute_overall_score_category(self):
        for record in self:
            score = record.overall_score
            if score < 35:
                record.overall_score_category = 'Deficiente'
            elif 35 <= score < 60:
                record.overall_score_category = 'Regular'
            elif 60 <= score < 90:
                record.overall_score_category = 'Bien'
            elif 90 <= score < 97:
                record.overall_score_category = 'Muy Bien'
            else:
                record.overall_score_category = 'Excelente'
