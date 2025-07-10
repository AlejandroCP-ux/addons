from odoo import http
from odoo.http import request
import requests
import logging

_logger = logging.getLogger(__name__)

class AlfrescoController(http.Controller):
    
    @http.route('/alfresco/file/<int:file_id>/preview', 
                type='http', auth='user', methods=['GET'])
    def preview_file(self, file_id, **kwargs):
        """Endpoint para mostrar preview de archivos PDF"""
        try:
            file_record = request.env['alfresco.file'].browse(file_id)
            if not file_record.exists():
                return request.not_found()
            
            config = request.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            if not all([url, user, pwd, file_record.alfresco_node_id]):
                return request.not_found()
            
            download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{file_record.alfresco_node_id}/content"
            response = requests.get(download_url, auth=(user, pwd), timeout=30)
            response.raise_for_status()
            
            return request.make_response(
                response.content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'inline; filename="{file_record.name}"'),
                ]
            )
            
        except Exception as e:
            _logger.error("Error sirviendo preview de archivo %s: %s", file_id, e)
            return request.not_found()
    
    @http.route('/alfresco/file/<int:file_id>/download', 
                type='http', auth='user', methods=['GET'])
    def download_file(self, file_id, **kwargs):
        """Endpoint para descargar archivos"""
        try:
            file_record = request.env['alfresco.file'].browse(file_id)
            if not file_record.exists():
                return request.not_found()
            
            config = request.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            if not all([url, user, pwd, file_record.alfresco_node_id]):
                return request.not_found()
            
            download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{file_record.alfresco_node_id}/content"
            response = requests.get(download_url, auth=(user, pwd), timeout=30)
            response.raise_for_status()
            
            return request.make_response(
                response.content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'attachment; filename="{file_record.name}"'),
                ]
            )
            
        except Exception as e:
            _logger.error("Error descargando archivo %s: %s", file_id, e)
            return request.not_found()
