from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def _get_default_localai_model(self):
        return self.env.ref('asi_ia.qwen2_1_5b_instruct').id
        
        
    module_asi_ia = fields.Boolean(
        string="Activar integración con IA"
    )    
    openapi_baseurl = fields.Char(string="Base URL", help="Provide the Base URL to local AI", config_parameter="asi_ia.openapi_base_url")
    openapi_api_key = fields.Char(string="API Key", help="Provide the API key here", config_parameter="asi_ia.openapi_api_key")
    localai_model_id = fields.Many2one('localai.model', 'Local AI Model', ondelete='cascade', default=_get_default_localai_model,  config_parameter="asi_ia.localai_model_id")

    localai_model_id = fields.Many2one('localai.model', string="AI Model")
    use_external_ia = fields.Boolean(string="Usar Endpoint Externo")
    external_ia_url = fields.Char(
        string="URL del Endpoint Externo",
        default="https://ia.asisurl.cu/webhook/chat",
        help="Endpoint para enviar mensajes a una IA externa"
    )

from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_external_ia = fields.Boolean(string="Usar Endpoint Externo")
    external_ia_url = fields.Char(
        string="URL del Endpoint Externo",
        default="https://ia.asisurl.cu/webhook/chat",
        help="Endpoint para enviar mensajes a una IA externa"
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        res.update(
            use_external_ia=IrConfig.get_param('asi_ia.use_external_ia', 'False') == 'True',
            external_ia_url=IrConfig.get_param('asi_ia.external_ia_url', 'https://ia.asisurl.cu/webhook/chat'),
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        IrConfig.set_param('asi_ia.use_external_ia', str(self.use_external_ia))
        IrConfig.set_param('asi_ia.external_ia_url', self.external_ia_url or '')



    def action_refresh_localai_models(self):
        self.ensure_one()
        if not self.openapi_baseurl:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Please set the Base URL first',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        try:
            Model = self.env['localai.model']
            if Model.refresh_models_from_lmstudio(self.openapi_baseurl):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'Models refreshed successfully',
                        'sticky': False,
                    }
                }
        except Exception as e:
            _logger.error(f"Error refreshing models: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Error',
                'message': 'Could not fetch models from LM Studio',
                'type': 'danger',
                'sticky': False,
            }
        }

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        IrConfig.set_param('asi_ia.openapi_baseurl', self.openapi_baseurl)
        IrConfig.set_param('asi_ia.localai_model_id', self.localai_model_id.id)
        IrConfig.set_param('asi_ia.use_external_ia', str(self.use_external_ia))
        IrConfig.set_param('asi_ia.external_ia_url', self.external_ia_url or '')


    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            openapi_baseurl=params.get_param('asi_ia.openapi_baseurl', default=''),
            localai_model_id=int(params.get_param('asi_ia.localai_model_id', default=0)),
            use_external_ia=params.get_param('asi_ia.use_external_ia', 'False') == 'True',
            external_ia_url=params.get_param('asi_ia.external_ia_url', 'https://ia.asisurl.cu/webhook/chat'),
        )
        return res