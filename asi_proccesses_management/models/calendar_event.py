from odoo import models, fields

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'
    
    x_process_id = fields.Many2one('x.process', string='Proceso Interno')