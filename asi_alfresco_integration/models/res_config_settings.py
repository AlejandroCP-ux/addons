from odoo import models, fields, api, _
import requests
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    alfresco_server_url = fields.Char(string="URL", config_parameter="asi_alfresco_integration.alfresco_server_url")
    alfresco_username = fields.Char(string="Usuario", config_parameter="asi_alfresco_integration.alfresco_username")
    alfresco_password = fields.Char(string="Contraseña",  config_parameter="asi_alfresco_integration.alfresco_password")
    alfresco_repo_id = fields.Char(string="Repo ID",  config_parameter="asi_alfresco_integration.alfresco_repo_id")

  
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('asi_alfresco_integration.alfresco_server_url', self.alfresco_server_url)
        self.env['ir.config_parameter'].set_param('asi_alfresco_integration.alfresco_username', self.alfresco_username)
        self.env['ir.config_parameter'].set_param('asi_alfresco_integration.alfresco_password', self.alfresco_password)
        self.env['ir.config_parameter'].set_param('asi_alfresco_integration.alfresco_repo_id', self.alfresco_repo_id)
    
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            alfresco_server_url=params.get_param('asi_alfresco_integration.alfresco_server_url', default=''),
            alfresco_username=params.get_param('asi_alfresco_integration.alfresco_username', default=''),
            alfresco_password=params.get_param('asi_alfresco_integration.alfresco_password', default=''),
            alfresco_repo_id=params.get_param('asi_alfresco_integration.alfresco_repo_id', default='-root-'),
            
        )
        return res
        
        
    def action_test_alfresco_connection(self):
        self.ensure_one()
        if not self.alfresco_server_url or not self.alfresco_username or not self.alfresco_password:
            raise UserError("Debe configurar la URL, usuario y contraseña de Alfresco antes de probar la conexión.")

        url = f"{self.alfresco_server_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/-root-/children"
        try:
            response = requests.get(url, auth=(self.alfresco_username, self.alfresco_password), timeout=10)
            response.raise_for_status()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Conexión exitosa',
                    'message': 'Se pudo conectar correctamente con Alfresco.',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Error al conectar con Alfresco: %s", e)
            raise UserError(f"Error al conectar con Alfresco:\n{e}")        
            

    def action_sync_alfresco_users(self):
        """Sincroniza todos los usuarios de Odoo con Alfresco"""
        try:
            # Obtener todos los usuarios activos (no compartidos)
            users = self.env['res.users'].search([
                ('active', '=', True),
                ('share', '=', False)
            ])
            
            if not users:
                raise UserError(_("No hay usuarios activos para sincronizar"))
            
            # Ejecutar la sincronización usando el método existente
            result = users.create_alfresco_user()
            
            # Mostrar notificación
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Proceso finalizado',
                    'sticky': False,
                }
                }
                
        except Exception as e:
            _logger.error("Error en sincronización: %s", str(e))                                   
            raise UserError(_("Error durante la sincronización: %s") % str(e))            