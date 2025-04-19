from odoo import models, api
from datetime import datetime

class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'
    
    @api.model

     def get_exception_dates(self):
        self.ensure_one()
        exceptions = set()
        for event in self.calendar_event_ids:
            if event.recurrence_id and event != event.recurrence_id.base_event_id:
                if event.start and isinstance(event.start, datetime):
                    start_date = event.start.date()
                    exceptions.add((start_date.year, start_date.month, start_date.day))
        return exceptions       