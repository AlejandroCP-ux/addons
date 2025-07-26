import logging
import requests
from openai import OpenAI
from odoo import models, _
from odoo.exceptions import UserError
import re
import json

_logger = logging.getLogger(__name__)

class IaService(models.AbstractModel):
    _name = 'asi_ia.service'
    _description = 'Servicio de conexión a IA (local o externa)'

    
    def get_ai_response(self, prompt):
        ICP = self.env['ir.config_parameter'].sudo()
        use_external = ICP.get_param('asi_ia.use_external_ia') == 'True'
        external_url = ICP.get_param('asi_ia.external_ia_url')
        prompt_ok = prompt + '. Responder en el idioma de la pregunta.'
        if use_external and external_url:
            response = self._get_external_response(prompt_ok, external_url)
            return response
        return self._get_local_response(prompt_ok)

    def _get_local_response(self, prompt):
        ICP = self.env['ir.config_parameter'].sudo()
        url = ICP.get_param('asi_ia.openapi_base_url')
        localai_model_id = ICP.get_param('asi_ia.localai_model')

        try:
            client = OpenAI(base_url=url, api_key="noapykey")
            localai_model = self.env['localai.model'].browse(int(localai_model_id)).name
        except Exception as ex:
            _logger.warning('Fallo al obtener modelo: %s', ex)
            localai_model = 'qwen2-0.5b-instruct'

        try:
            _logger.info('Prompt enviado a IA local: %s', prompt)
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": prompt}],
                model=localai_model,
                temperature=0.6,
                max_tokens=3000,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                user=self.env.user.name,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise UserError(_('Error en respuesta IA local: %s') % str(e))

    

    def _get_external_response(self, prompt, url):
        try:
            _logger.info('Prompt enviado a IA externa: %s , url : %s', prompt, url)
            response = requests.post(
                url,
                json={"prompt": prompt},
                headers={"Content-Type": "application/json"},
                timeout=60,
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    # Asumimos que la respuesta es una lista de diccionarios
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                        return data[0].get("output", "")
                    else:
                        raise UserError(_('La respuesta JSON no es una lista de diccionarios válida: %s') % str(data))
                except ValueError:
                    raise UserError(_('La respuesta de la IA no es JSON válido. Contenido recibido: %s') % response.text)
            else:
                raise UserError(_('Error en respuesta IA externa: Código %s - %s') % (response.status_code, response.text))

        except Exception as e:
            raise UserError(_('Error de conexión a IA externa: %s') % str(e))


