# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests
import json
import logging
from openai import OpenAI

_logger = logging.getLogger(__name__)


class CalendarWorkplanEvaluation(models.Model):
    _name = 'calendar_workplan.evaluation'
    _description = 'Evaluación del cumplimiento del plan de trabajo con IA'

    plan_id = fields.Many2one('calendar_workplan.plan', string="Plan de trabajo", required=True)
    evaluation_date = fields.Datetime(string="Fecha de evaluación", default=fields.Datetime.now)
    quantitative_score = fields.Float("Puntuación cuantitativa")
    compliance_percentage = fields.Float("Porcentaje de cumplimiento")
    qualitative_analysis = fields.Text("Análisis cualitativo")

    @api.model
    def generate_evaluation(self, plan_id):
        plan = self.env['calendar_workplan.plan'].browse(plan_id)
        events = plan.inherited_meeting_ids.filtered(lambda e: e.start and e.start < fields.Datetime.now())
    
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
    
        prompt_header = f"""
        Eres un analista experto en productividad y gestión de trabajo asistido por IA.
        
        A continuación se listan los eventos principales (prioridad 1) planificados en un plan de trabajo. Cada evento tiene su fecha programada, la sección responsable, y un indicador de si hubo participación registrada (realizado: Sí/No).
        
        Tu tarea es evaluar la participación en estos eventos desde dos perspectivas:
        
        1. Análisis Cuantitativo:
           - Calcula el porcentaje general de participación (eventos con participación frente al total).
           - Indica cuántos eventos se cumplieron y cuántos no.
           - Desglosa la participación por sección.
        
        2. Análisis Cualitativo:
           - Evalúa la consistencia de la participación a lo largo del tiempo.
           - Comenta sobre posibles causas del incumplimiento.
           - Emite observaciones sobre el desempeño general.
        
        3. Resultado Esperado:
           - Porcentaje total de cumplimiento.
           - Puntuación general (0 a 10).
           - Comentario cualitativo.
           - Recomendaciones.
        
        Eventos a evaluar:
        """
      
        prompt = prompt_header + "\n" + "\n".join(event_lines)
          
        # Registrar nota con el prompt
        plan.message_post(
            body=f"<b>Prompt usado para la evaluación IA:</b><br/><pre>{prompt}</pre>",
            subtype_xmlid="mail.mt_note"
        )
    
        # Lógica de conexión al modelo IA
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('asi_ia.openapi_api_key')
        url = ICP.get_param('asi_ia.openapi_base_url')
        _logger.warning('***->url del endpoint: %s' % url)
        client = OpenAI(base_url=url, api_key="noapykey")
        localai_model_id = ICP.get_param('asi_ia.localai_model')
    
        try:
            if localai_model_id:
                localai_model = self.env['localai.model'].browse(int(localai_model_id)).name
                _logger.warning('***->va a usar el modelo: %s' % localai_model)
    
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=localai_model,
                    temperature=0.6,
                    max_tokens=3000,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                    user=self.env.user.name
                )
                res = response.choices[0].message.content
                _logger.warning('------->A fajarse con LLMStudio...  Respuesta: %s ', res)
                if res:
                    return res
                else:
                    raise Exception(f"Error del modelo IA: {response.text}")
        except Exception as e:
            raise models.UserError(f"No se pudo obtener la evaluación: {str(e)}")