from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class LocalAIModel(models.Model):
    _name = 'localai.model'
    _description = 'Local AI Models'

    name = fields.Char(required=True)
    model_id = fields.Char(string='Model ID')
    is_active = fields.Boolean(default=True)

    @api.model
    def refresh_models_from_lmstudio(self, base_url):
        try:
            if not base_url:
                _logger.error("No base URL provided for LM Studio")
                return False

            response = requests.get(f"{base_url.rstrip('/')}/models", timeout=10)
            if response.status_code == 200:
                models_data = response.json()
                current_models = {m.model_id: m for m in self.search([])}
                
                # Actualizar/crear modelos
                for model_data in models_data.get('data', []):
                    model_id = model_data.get('id')
                    if not model_id:
                        continue
                        
                    vals = {
                        'name': model_data.get('name', model_id),
                        'model_id': model_id,
                        'is_active': True
                    }
                    
                    if model_id in current_models:
                        current_models[model_id].write(vals)
                    else:
                        self.create(vals)
                
                return True
            else:
                _logger.error(f"LM Studio API returned status {response.status_code}")
        except requests.exceptions.RequestException as e:
            _logger.error(f"Connection error to LM Studio: {str(e)}")
        except Exception as e:
            _logger.error(f"Unexpected error: {str(e)}")
        
        return False