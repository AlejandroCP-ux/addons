# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import unicodedata

_logger = logging.getLogger(__name__)

class PerformanceEvaluationSummaryWizard(models.TransientModel):
    _name = 'performance.evaluation.summary.wizard'
    _description = 'Wizard to generate summary of evaluations for subordinates'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True)
    performance_period_id = fields.Many2one('performance.period', string='Período', required=True)

    def get_report_file_name(self):
        self.ensure_one()
        periodo = self.performance_period_id.name or 'Periodo'
        departamento = self.employee_id.department_id.name or 'Departamento'
        return f"Reporte de evaluación - {periodo} - {departamento}"

    def _get_subordinates(self):
        self.ensure_one()
        # Direct subordinates: employees whose parent_id is the selected employee
        subs = self.env['hr.employee'].search([('parent_id', '=', self.employee_id.id)], order='id')
        return subs

    def _gather_evaluations(self):
        self.ensure_one()
        subs = self._get_subordinates()
        if not subs:
            return []
        evals = self.env['performance.evaluation.program'].search([
            ('employee_id', 'in', subs.ids),
            ('performance_period_id', '=', self.performance_period_id.id)
        ])
        # Map evaluations by employee id (take latest if multiple)
        result = {}
        for ev in evals.sorted(key=lambda r: r.date_of_evaluation or False, reverse=True):
            if ev.employee_id.id not in result:
                result[ev.employee_id.id] = ev
        # Return list preserving subordinate order
        return [result.get(emp.id) for emp in subs]
    
    
        fields_to_check = {
            'Empleado': self.employee_id.name,
            'Departamento': self.employee_id.department_id.name,
            'Periodo': self.performance_period_id.name,
        }

        for label, value in fields_to_check.items():
            check_string(label, value)

        for sub in self._get_subordinates():
            check_string(f"Subordinado: {sub.name}", sub.name)
            check_string(f"Cargo: {sub.name}", sub.job_id.name)
    
    def action_print_report(self):
        self.ensure_one()
        ref = self.env.ref('performance_evaluation_summary.report_performance_summary', False)
        if not ref:
            raise UserError(_('Report XML ID not found: performance_evaluation_summary.report_performance_summary'))
        return ref.with_context(company=self.env.company).report_action(self)
