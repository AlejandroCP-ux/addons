# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition
import base64
import logging

_logger = logging.getLogger(__name__)

class SignatureWorkflowController(http.Controller):
    
    @http.route('/signature_workflow/download_signed/<int:workflow_id>', type='http', auth='user')
    def download_signed_documents(self, workflow_id, **kwargs):
        """Controlador para mostrar página de descarga de documentos firmados individuales"""
        try:
            workflow = request.env['signature.workflow'].browse(workflow_id)
            
            if not workflow.exists():
                return request.not_found()
            
            # Verificar permisos (solo creador o destinatario pueden descargar)
            if request.env.user not in (workflow.creator_id, workflow.target_user_id):
                return request.redirect('/web/login')
            
            if workflow.state != 'completed':
                return request.not_found()
            
            return request.render('asi_signature_workflow.download_signed_documents_page', {
                'workflow': workflow,
                'signed_documents': workflow.document_ids.filtered('is_signed'),
            })
            
        except Exception as e:
            _logger.error(f"Error accediendo a documentos del flujo {workflow_id}: {e}")
            return request.not_found()

    @http.route('/signature_workflow/document/<int:document_id>/download', type='http', auth='user')
    def download_single_document(self, document_id, **kwargs):
        """Controlador para descargar un documento individual firmado"""
        try:
            document = request.env['signature.workflow.document'].browse(document_id)
            
            if not document.exists() or not document.is_signed:
                return request.not_found()
            
            workflow = document.workflow_id
            
            # Verificar permisos
            if request.env.user not in (workflow.creator_id, workflow.target_user_id):
                return request.redirect('/web/login')
            
            # Descargar según el tipo de documento
            if workflow.document_source == 'alfresco' and document.alfresco_file_id:
                return self._download_alfresco_document(document.alfresco_file_id)
            elif document.pdf_content:
                return self._download_local_document(document)
            else:
                _logger.warning(f"No se encontró ruta de descarga para documento {document_id}: alfresco_file_id={document.alfresco_file_id}, pdf_content={'Sí' if document.pdf_content else 'No'}")
                return request.not_found()
                
        except Exception as e:
            _logger.error(f"Error descargando documento {document_id}: {e}")
            return request.not_found()

    def _download_alfresco_document(self, alfresco_file):
        """Descarga un documento de Alfresco"""
        try:
            config = request.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            if not all([url, user, pwd]):
                _logger.error("Configuración de Alfresco incompleta para descarga")
                return request.not_found()
            
            import requests
            
            download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{alfresco_file.alfresco_node_id}/content"
            response = requests.get(download_url, auth=(user, pwd), timeout=30)
            
            if response.status_code == 200:
                headers = [
                    ('Content-Type', 'application/pdf'),
                    ('Content-Length', len(response.content)),
                    ('Content-Disposition', f'attachment; filename="{alfresco_file.name}"'),
                ]
                return request.make_response(response.content, headers=headers)
            else:
                _logger.error(f"Error descargando de Alfresco: HTTP {response.status_code}")
                return request.not_found()
                
        except Exception as e:
            _logger.error(f"Error descargando de Alfresco: {e}")
            return request.not_found()

    def _download_local_document(self, document):
        """Descarga un documento local"""
        try:
            if not document.pdf_content:
                _logger.error(f"Documento {document.id} no tiene contenido PDF")
                return request.not_found()
                
            pdf_content = base64.b64decode(document.pdf_content)
            
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="{document.name}"'),
            ]
            
            return request.make_response(pdf_content, headers=headers)
            
        except Exception as e:
            _logger.error(f"Error descargando documento local: {e}")
            return request.not_found()
