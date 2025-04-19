from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    workplan_planner_partner_id = fields.Many2one(
        'res.partner', 
        string='Default Workplan Planner',
        help="Default partner who presents workplans for this company"
    )
    workplan_approver_partner_id = fields.Many2one(
        'res.partner', 
        string='Default Workplan Approver',
        help="Default partner who approves workplans for this company"
    )