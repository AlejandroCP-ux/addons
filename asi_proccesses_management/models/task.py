from odoo import models, fields

class ProjectTask(models.Model):
    _inherit = 'project.task'

    asi_process_id = fields.Many2one('asi.process', string='Related Process')
