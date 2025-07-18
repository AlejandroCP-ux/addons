import requests
import re
import secrets
import string
from odoo import models, api, _, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    
    def _get_alfresco_config(self):
        """Obtiene y valida configuracion de Alfresco"""
        RCS = self.env['ir.config_parameter'].sudo()
        config = {
            'server_url': RCS.get_param('asi_alfresco_integration.alfresco_server_url'),
            'username': RCS.get_param('asi_alfresco_integration.alfresco_username'),
            'password': RCS.get_param('asi_alfresco_integration.alfresco_password'),
            'repo_id': RCS.get_param('asi_alfresco_integration.alfresco_repo_id'),
        }
        
        missing = [k for k, v in config.items() if not v]
        if missing:
            raise UserError(_("Faltan parametros de Alfresco: %s") % ", ".join(missing))
            
        if not config['server_url'].startswith(('https://', 'http://')):
            raise UserError(_("URL de Alfresco debe incluir protocolo (http:// o https://)"))
            
        return config

    def _generate_secure_password(self):
        """Genera contrasenna segura de 12 caracteres"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(12))

    def _validate_email_basic(self, email):
        """Validaci0n basica de formato email con regex"""
        if not email:
            return False
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return True

    def _prepare_alfresco_payload(self, user):
        """Prepara datos del usuario con validacion basica de email"""
        # Validar y obtener email
        email = user.email or f"{user.login}@asisurl.cu"
        if not self._validate_email_basic(email):
            email = f"{user.login}@asisurl.cu"
    
        # Separar nombre y apellido
        name_parts = user.name.split(' ', 1) if user.name else ["Nombre", "Apellido"]
        first_name = name_parts[0] or "Nombre"
        last_name = name_parts[1] if len(name_parts) > 1 else "Apellido"
    
        # Asegurar que jobTitle sea string
        job_title = 'No definida'
        if user.partner_id and user.partner_id.function:
            job_title = str(user.partner_id.function)
    
        # Asegurar que company sea string
        company_name = 'No definida'
        if user.partner_id and user.partner_id.company_id and user.partner_id.company_id.name:
            company_name = str(user.partner_id.company_id.name)
    
        return {
            "id": user.login,
            "firstName": first_name,
            "lastName": last_name,
            "email": email, 
            "jobTitle": job_title,
            "company": {
                "organization": company_name
            },
            "password": 'Pass1234'
        }

    def _handle_alfresco_response(self, user, response):
        """Maneja respuestas de la API de Alfresco"""
        if response.status_code == 201:
            _logger.info("Usuario %s creado en Alfresco", user.login)
            return True
        elif response.status_code == 409:
            _logger.warning("Usuario %s ya existe en Alfresco", user.login)
            return False
        else:
            error_msg = _("Error creando usuario %s: [%s] %s") % (
                user.login, 
                response.status_code, 
                response.text[:100]
            )
            _logger.error(error_msg)
            raise UserError(error_msg)

    def create_alfresco_user(self):
        """Crea usuario en Alfresco con manejo mejorado de errores"""
        config = self._get_alfresco_config()
        url = f"{config['server_url']}/alfresco/api/-default-/public/alfresco/versions/1/people"
        auth = (config['username'], config['password'])
        
        success_users = self.env['res.users']
        
        for user in self.filtered(lambda u: u.active and not u.share):
            try:
                payload = self._prepare_alfresco_payload(user)
                
                try:
                    response = requests.post(
                        url,
                        auth=auth,
                        json=payload,
                        timeout=10,
                        verify=True
                    )
                except requests.RequestException as e:
                    _logger.error("Error de conexion para %s: %s", user.login, str(e))
                    continue
                    
                if self._handle_alfresco_response(user, response):
                    user.sudo().write({
                        'alfresco_password': payload['password']
                    })
                    success_users += user
                    
            except Exception as e:
                _logger.exception("Error inesperado con %s: %s", user.login, str(e))
                continue
        
        if success_users:
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': _("Usuarios creados en Alfresco: %s") % ", ".join(
                        success_users.mapped('login')
                    ),
                    'type': 'rainbow_man',
                }
            }
        return False