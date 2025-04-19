from odoo import models, fields, api

class ExtendedEvent(models.Model):
    _inherit = 'calendar.event'

    STATE_SELECTION = [
        ('needsAction', 'Needs Action'),
        ('tentative', 'Uncertain'),
        ('declined', 'Declined'),
        ('accepted', 'Accepted'),
        ('done', 'Done'), 
        ('not_attended', 'Not attended'),        
    ]

    state = fields.Selection(STATE_SELECTION, string='State', default='needsAction')

 # Función para marcar un evento como cumplido o incumplido
 
    @api.model
    def action_done(self):
        self.write({'state': 'done'})
        return True

    @api.model
    def action_not_attended(self):
        self.write({'state': 'not_attended'})
        return True

class CalendarEventCompletion(models.Model):
    _name = 'calendar.event.completion'

    event_id = fields.Many2one('calendar.event', string='Evento')
    user_id = fields.Many2one('res.users', string='Usuario')
    completion_date = fields.Date(string='Fecha de cumplimiento')

    @api.model
    def create(self, vals):
        event = self.env['calendar.event'].browse(vals['event_id'])

        # Si al menos un asistente marca el evento como cumplido, se marca como cumplido
        if event.completion_ids:
            event.write({'state': 'done'})

        return super(CalendarEventCompletion, self).create(vals)
