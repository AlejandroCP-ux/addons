# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ScheduledTask(models.Model):
    _name = 'it.scheduled.task'
    _description = 'Tarea Programada de TI'

    name = fields.Char(string='Nombre de la Tarea', required=True)
    active = fields.Boolean(default=True)

    # COMENTARIO: La selección de acciones también será extensible.
    # Cada módulo podrá añadir sus propias acciones programadas.
    action_type = fields.Selection(
        selection=[
            ('incident_report', 'Reporte de Incidentes'),
            # Los módulos de hardware, red, etc., añadirán sus propias acciones aquí.
            # ej: ('network_scan', 'Escaneo de Red') desde sgich_red
        ],
        string='Tipo de Acción',
        required=True
    )

    cron_id = fields.Many2one('ir.cron', string='Trabajo Cron', readonly=True)
    last_execution = fields.Datetime(string='Última Ejecución', readonly=True)
    next_execution = fields.Datetime(string='Próxima Ejecución', related='cron_id.nextcall', readonly=True)

    def run_task(self):
        """
        COMENTARIO: Al igual que en el backlog, este método será extendido.
        Cada módulo se encargará de implementar la lógica para sus
        propios tipos de acción.
        """
        self.ensure_one()
        if self.action_type == 'incident_report':
            self._run_incident_report()
        else:
            # Permitir que otros módulos manejen sus acciones
            # super(ScheduledTask, self).run_task()
            raise NotImplementedError(_("La acción '%s' no está implementada.") % self.action_type)

    def _run_incident_report(self):
        # Lógica para generar y enviar un reporte de incidentes.
        # (Implementación de ejemplo)
        incidents = self.env['it.incident'].search([('status', '!=', 'closed')])
        # ... generar PDF o email ...
        pass