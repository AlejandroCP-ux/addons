from odoo import models, fields

class XProcess(models.Model):
    _name = 'x.process'
    _description = 'Proceso Interno'

    name = fields.Char(string='Nombre del Proceso', required=True)
    department_id = fields.Many2one('hr.department', string='Departamento', required=True)
    user_id = fields.Many2one('res.users', string='Responsable', required=True)
    objective = fields.Char(string='Misión del Proceso', required=True)
   
    event_ids = fields.One2many('calendar.event', 'x_process_id', string='Eventos de Calendario')
