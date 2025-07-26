# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
class CalendarWorkplanPlan(models.Model):
    _inherit = 'calendar_workplan.plan'
    
    qualitative_analysis = fields.Text("Análisis cualitativo")

    def _get_evaluation_prompt(self):
        self.ensure_one()
        events = self.inherited_meeting_ids.filtered(lambda e: e.start and e.start < fields.Datetime.now())

        event_lines = []
        for event in events:
            realizado = 'Sí' if any(att.has_participated for att in event.attendee_ids) else 'No'
            event_lines.append(
                f"- [Nombre: {event.name}, "
                f"Planificado: {event.start.strftime('%Y-%m-%d')}, "
                f"Realizado: {realizado}, "
                f"Sección: {event.section_id.name if event.section_id else 'N/A'}, "
                f"Prioridad: {event.priority}]"
            )

        prompt_header = """
Eres un analista experto en productividad y gestión de trabajo asistido por IA.
A continuación se listan los eventos planificados en un plan de trabajo. Cada evento tiene su fecha programada, la sección responsable, y un indicador de si hubo participación registrada (realizado: Sí/No). 
Existen eventos con prioridad 1, que son actividades principales dentro del mes.

Tu tarea es evaluar la participación en estos eventos desde dos perspectivas:

1. Análisis Cuantitativo:
   - Calcula el porcentaje general de participación (eventos con participación frente al total).
   - Indica cuántos eventos se cumplieron y cuántos no.
   - Desglosa la participación por sección.

2. Análisis Cualitativo:
   - Evalúa la consistencia de la participación a lo largo del tiempo.
   - Comenta sobre posibles causas del incumplimiento.
   - Emite observaciones sobre el desempeño general.

Con esta información, evalúa el desempeño en el período que comprenden las tareas, haciendo énfasis en:
   - Porcentaje total de cumplimiento.
   - Puntuación general (0 a 10).
   - Comentario cualitativo.
   - Recomendaciones a tener en cuenta para futuros períodos.

Eventos a evaluar:
"""
        prompt = prompt_header + "\n" + "\n".join(event_lines)

        # Registrar el prompt como nota en el plan
        self.message_post(
            body=f"<b>Prompt usado para la evaluación IA:</b><br/><pre>{prompt}</pre>",
            subtype_xmlid="mail.mt_note"
        )

        try:
            response = self.env['asi_ia.service'].get_ai_response(prompt)
            self.qualitative_analysis = response
            return response
        except Exception as e:
            raise UserError(_("No se pudo obtener la evaluación: %s") % str(e))

    def action_generate_evaluation(self):
        for record in self:
            prompt = record._get_evaluation_prompt()
            response = self.env['asi_ia.service'].get_ai_response(prompt)
            record.qualitative_analysis = response
        return True    