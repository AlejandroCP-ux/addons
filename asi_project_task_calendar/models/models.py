# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    event_id = fields.Many2one('calendar.event', string="Calendario Evento")

    def create_calendar_event(self):
        for task in self:
            if task.user_ids:
                tag = self.env['calendar.event.type'].search([('name', '=', 'Trabajo en Proyectos')], limit=1)
                if not tag:
                    tag = self.env['calendar.event.type'].create({'name': 'Trabajo en Proyectos'})
                partners = task.user_ids.partner_id | task.user_ids.partner_id.child_ids
                attendees = [(4, partner.id) for partner in partners]
                event_values = {
                    'name': f"Tarea: {task.project_id.name}-{task.name}",
                    'start_date': task.date_deadline,
                    'stop_date': task.date_deadline,
                    'allday': True,
                    'user_id': self.env.uid,
                    'partner_ids': attendees,    
                    'categ_ids': [(4, tag.id)] ,            
                }
                self.env['calendar.event'].create(event_values)

    @api.model
    def create(self, values):
        task = super(ProjectTask, self).create(values)
        task.create_calendar_event()
        return task


    def action_complete_task(self):
        super().action_complete()
        if self.event_id:
            self.event_id.write({'completed': True})

    @api.onchange('user_id')
    def onchange_user_id(self):
        if self.event_id:
            self.event_id.write({'user_id': self.user_id.id})

    def mark_done(self):
        for task in self:
            if task.event_id:
                task.event_id.write({'done': True})
            super(ProjectTask, task).mark_done()

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    task_id = fields.Many2one('project.task', string="Tarea Proyecto")

    @api.depends('task_id', 'task_id.name')
    def _compute_name(self):
        for record in self:
            if record.task_id:
                record.name = f"{record.task_id.project_id.name} - {record.task_id.name}"
            else:
                record.name = "Calendar Event"

