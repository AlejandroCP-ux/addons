from odoo import models, fields

class AlfrescoConfig(models.Model):
    _name = 'alfresco.config'
    _description = 'Configuración del servidor Alfresco'

    name = fields.Char(default="Configuración Alfresco")
    server_url = fields.Char(string="URL del Servidor", required=True)
    username = fields.Char(string="Usuario", required=True)
    password = fields.Char(string="Contraseña", required=True)
    repo_id = fields.Char(string="ID del repositorio", required=True)
