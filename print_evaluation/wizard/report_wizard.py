from odoo import models, fields, api

class PerformanceReportWizard(models.TransientModel):
    _name = 'performance.report.wizard'
    _description = 'Wizard para filtrar reporte de evaluación'

    performance_period_id = fields.Many2one(
        'performance.period', 
        string='Período', 
        required=True
    )
    department_id = fields.Many2one(
        'hr.department', 
        string='Departamento', 
        required=True
    )

    def action_generate_report(self):
        # Obtener los registros filtrados
        evaluations = self.env['performance.evaluation.program'].search([
            ('performance_period_id', '=', self.performance_period_id.id),
            ('department_id', '=', self.department_id.id),
            ('state', '=', 'done')  # Solo evaluaciones completadas
        ])
        
        # Generar el reporte
        return self.env.ref('print_evaluation.print_evaluation_report').report_action(evaluations)
    
    def action_generate_report_list(self):
        # Obtener los registros filtrados
        evaluations = self.env['performance.evaluation.program'].search([
            ('performance_period_id', '=', self.performance_period_id.id),
            ('department_id', '=', self.department_id.id),
            ('state', '=', 'done')  # Solo evaluaciones completadas
        ])
        
        # Generar el reporte
        return self.env.ref('print_evaluation.print_evaluation_report_list').report_action(evaluations)

