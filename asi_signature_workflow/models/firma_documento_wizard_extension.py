# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class FirmaDocumentoWizardExtension(models.TransientModel):
    _inherit = 'firma.documento.wizard'
    
    from_workflow = fields.Boolean(string='Desde Flujo de Trabajo', default=False)
    workflow_id = fields.Many2one('signature.workflow', string='Flujo de Trabajo')
    readonly_signature_config = fields.Boolean(string='Configuración de Solo Lectura', default=False)

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente"""
        res = super(FirmaDocumentoWizardExtension, self).default_get(fields_list)
        
        context = self.env.context
        if context.get('from_workflow') and context.get('workflow_id'):
            workflow = self.env['signature.workflow'].browse(context.get('workflow_id'))
            if workflow.exists():
                res.update({
                    'from_workflow': True,
                    'workflow_id': workflow.id,
                    'readonly_signature_config': context.get('readonly_signature_config', False),
                })
                
                # Solo asignar signature_role si está en la lista de campos solicitados
                if 'signature_role' in fields_list and workflow.signature_role_id:
                    res['signature_role'] = workflow.signature_role_id.id
                
                # Solo asignar signature_position si está en la lista de campos solicitados  
                if 'signature_position' in fields_list and workflow.signature_position:
                    res['signature_position'] = workflow.signature_position
                
                _logger.info(f"Wizard de firma local configurado desde flujo {workflow.id} con rol {workflow.signature_role_id.name if workflow.signature_role_id else 'N/A'} y posición {workflow.signature_position}")
        
        return res

    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        try:
            result = super(FirmaDocumentoWizardExtension, self).action_firmar_documentos()
            
            # Solo procesar el flujo si la firma fue exitosa
            if self.from_workflow and self.workflow_id and self.status == 'completado':
                try:
                    self._upload_signed_documents_to_alfresco()
                    
                    self.workflow_id.action_mark_as_signed()
                    _logger.info(f"Flujo {self.workflow_id.id} marcado como firmado automáticamente")
                except Exception as e:
                    _logger.error(f"Error marcando flujo como firmado: {e}")
                    # No re-lanzar el error para no afectar la firma exitosa
            
            return result
            
        except Exception as e:
            _logger.error(f"Error en action_firmar_documentos desde flujo {self.workflow_id.id if self.workflow_id else 'N/A'}: {e}")
            # Re-lanzar el error original para que el usuario lo vea
            raise

    def _upload_signed_documents_to_alfresco(self):
        """Sube los documentos firmados de vuelta a Alfresco como nuevas versiones"""
        if not self.from_workflow or not self.workflow_id:
            return
            
        _logger.info(f"Iniciando subida de documentos firmados a Alfresco para flujo {self.workflow_id.id}")
        
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            if not all([url, user, pwd]):
                _logger.error("Configuración de Alfresco incompleta para subir documentos firmados")
                return
            
            import requests
            import base64
            
            _logger.info(f"Documentos firmados encontrados: {len(self.document_ids.filtered(lambda d: d.pdf_signed))}")
            _logger.info(f"Documentos en el flujo: {len(self.workflow_id.document_ids)}")
            
            for workflow_doc in self.workflow_id.document_ids:
                _logger.info(f"Documento flujo: {workflow_doc.name}, tiene alfresco_file_id: {bool(workflow_doc.alfresco_file_id)}")
                if workflow_doc.alfresco_file_id:
                    _logger.info(f"  - alfresco_node_id actual: {workflow_doc.alfresco_file_id.alfresco_node_id}")
                    _logger.info(f"  - nombre: {workflow_doc.alfresco_file_id.name}")
                    
                    # Buscar el ID real del documento en Alfresco
                    real_node_id = self._find_real_alfresco_node_id(workflow_doc.alfresco_file_id.name, workflow_doc.workflow_id.alfresco_folder_id)
                    if real_node_id and real_node_id != workflow_doc.alfresco_file_id.alfresco_node_id:
                        _logger.info(f"  - ID real encontrado: {real_node_id}, actualizando registro")
                        workflow_doc.alfresco_file_id.write({'alfresco_node_id': real_node_id})
                    elif not real_node_id:
                        _logger.warning(f"  - No se pudo encontrar ID real para {workflow_doc.alfresco_file_id.name}")
            
            # Procesar cada documento firmado
            for doc_line in self.document_ids.filtered(lambda d: d.pdf_signed):
                try:
                    _logger.info(f"Procesando documento firmado: {doc_line.document_name}")
                    
                    # Buscar el documento correspondiente en el flujo
                    workflow_doc = self.workflow_id.document_ids.filtered(lambda wd: wd.name == doc_line.document_name)
                    
                    if not workflow_doc:
                        _logger.warning(f"No se encontró documento del flujo para {doc_line.document_name}")
                        base_name = doc_line.document_name.replace('.pdf', '') if doc_line.document_name.endswith('.pdf') else doc_line.document_name
                        workflow_doc = self.workflow_id.document_ids.filtered(lambda wd: wd.name.replace('.pdf', '') == base_name)
                        
                        if workflow_doc:
                            _logger.info(f"Encontrado documento por nombre base: {workflow_doc[0].name}")
                        else:
                            _logger.error(f"No se pudo encontrar documento del flujo para {doc_line.document_name}")
                            continue
                    
                    workflow_doc = workflow_doc[0]  # Tomar el primero si hay múltiples
                    
                    if not workflow_doc.alfresco_file_id:
                        _logger.error(f"Documento {doc_line.document_name} no tiene archivo de Alfresco asociado")
                        continue
                    
                    node_id = workflow_doc.alfresco_file_id.alfresco_node_id
                    _logger.info(f"Usando node_id: {node_id} para documento {doc_line.document_name}")
                    
                    check_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}"
                    check_response = requests.get(check_url, auth=(user, pwd), timeout=10)
                    
                    if check_response.status_code != 200:
                        _logger.error(f"El nodo {node_id} no existe en Alfresco: {check_response.status_code} - {check_response.text}")
                        continue
                    
                    # Obtener el contenido del documento firmado
                    signed_pdf_data = base64.b64decode(doc_line.pdf_signed)
                    _logger.info(f"Tamaño del PDF firmado: {len(signed_pdf_data)} bytes")
                    
                    update_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
                    
                    _logger.info(f"Actualizando contenido de documento {doc_line.document_name} en nodo {node_id}")
                    _logger.info(f"URL de actualización: {update_url}")
                    
                    response = requests.put(
                        update_url,
                        headers={"Content-Type": "application/pdf"},
                        data=signed_pdf_data,
                        auth=(user, pwd),
                        timeout=30
                    )
                    
                    _logger.info(f"Respuesta de actualización: {response.status_code}")
                    
                    if response.status_code == 200:
                        _logger.info(f"Documento firmado {doc_line.document_name} actualizado exitosamente")
                        
                        workflow_doc.write({
                            'is_signed': True,
                            'signed_date': fields.Datetime.now(),
                        })
                        
                        # Actualizar también el registro de alfresco.file con la nueva fecha de modificación
                        workflow_doc.alfresco_file_id.write({
                            'modified_at': fields.Datetime.now(),
                            'file_size': len(signed_pdf_data)
                        })
                        
                    else:
                        _logger.error(f"Error actualizando documento firmado {doc_line.document_name}: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    _logger.error(f"Error procesando documento firmado {doc_line.document_name}: {e}")
                    import traceback
                    _logger.error(f"Traceback: {traceback.format_exc()}")
                    continue
            
            _logger.info(f"Proceso de subida de documentos firmados completado para flujo {self.workflow_id.id}")
            
        except Exception as e:
            _logger.error(f"Error general subiendo documentos firmados a Alfresco: {e}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            # No lanzar excepción para no interrumpir el flujo de firma

    def _find_real_alfresco_node_id(self, file_name, workflow_folder):
        """Busca el ID real del documento en Alfresco por nombre y carpeta"""
        if not workflow_folder:
            _logger.warning(f"No hay carpeta de flujo para buscar {file_name}")
            return None
            
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            if not all([url, user, pwd]):
                return None
            
            import requests
            
            search_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{workflow_folder.node_id}/children"
            search_params = {
                'where': "(nodeType='cm:content')",  # Solo filtrar por tipo de contenido
                'maxItems': 100  # Aumentar límite para asegurar que encontremos el archivo
            }
            
            _logger.info(f"Buscando archivo {file_name} en carpeta {workflow_folder.node_id}")
            _logger.info(f"URL de búsqueda: {search_url}")
            _logger.info(f"Parámetros: {search_params}")
            
            search_response = requests.get(
                search_url,
                params=search_params,
                auth=(user, pwd),
                timeout=30
            )
            
            _logger.info(f"Respuesta de búsqueda: {search_response.status_code}")
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                _logger.info(f"Archivos encontrados en carpeta: {len(search_data.get('list', {}).get('entries', []))}")
                
                for entry in search_data.get('list', {}).get('entries', []):
                    file_info = entry['entry']
                    if file_info.get('name') == file_name:
                        real_node_id = file_info['id']
                        _logger.info(f"ID real encontrado para {file_name}: {real_node_id}")
                        return real_node_id
                
                _logger.warning(f"No se encontró archivo {file_name} en la carpeta del flujo")
                for entry in search_data.get('list', {}).get('entries', []):
                    file_info = entry['entry']
                    _logger.info(f"  - Archivo encontrado: {file_info.get('name')} (ID: {file_info.get('id')})")
                return None
            else:
                _logger.error(f"Error buscando archivo {file_name}: {search_response.status_code} - {search_response.text}")
                return None
                
        except Exception as e:
            _logger.error(f"Excepción buscando ID real para {file_name}: {e}")
            return None

    @api.onchange('signature_role', 'signature_position')
    def _onchange_signature_config(self):
        """Prevenir cambios en configuración cuando viene de flujo de trabajo"""
        if self.readonly_signature_config and self.from_workflow:
            if self.workflow_id:
                if self.workflow_id.signature_role_id:
                    self.signature_role = self.workflow_id.signature_role_id.id
                if self.workflow_id.signature_position:
                    self.signature_position = self.workflow_id.signature_position
                return {
                    'warning': {
                        'title': _('Configuración Bloqueada'),
                        'message': _('El rol y posición de firma están definidos por el creador del flujo de trabajo y no pueden ser modificados.')
                    }
                }
