# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class SignatureWorkflow(models.Model):
    _name = 'signature.workflow'
    _description = 'Flujo de Trabajo de Firma Digital'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Nombre del Flujo', required=True)
    creator_id = fields.Many2one('res.users', string='Creador', required=True, default=lambda self: self.env.user)
    target_user_id = fields.Many2one('res.users', string='Usuario Destinatario', required=True)
    signature_role_id = fields.Many2one('document.signature.tag', string='Rol de Firma', required=True)
    signature_position = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma', required=True, default='derecha')
    
    document_source = fields.Selection([
        ('local', 'Documentos Locales'),
        ('alfresco', 'Documentos de Alfresco')
    ], string='Origen de Documentos', required=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('signed', 'Firmado'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', required=True, tracking=True)
    
    # Documentos del flujo
    document_ids = fields.One2many('signature.workflow.document', 'workflow_id', string='Documentos')
    document_count = fields.Integer(string='Cantidad de Documentos', compute='_compute_document_count')
    
    alfresco_folder_id = fields.Many2one('alfresco.folder', string='Carpeta del Flujo en Alfresco', readonly=True)
    
    # Fechas importantes
    sent_date = fields.Datetime(string='Fecha de Envío')
    signed_date = fields.Datetime(string='Fecha de Firma')
    completed_date = fields.Datetime(string='Fecha de Finalización')
    
    # Notas y observaciones
    notes = fields.Text(string='Notas')
    signature_notes = fields.Text(string='Notas de Firma', readonly=True)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    @api.model
    def create(self, vals):
        """Override create para subir documentos locales a Alfresco automáticamente"""
        workflow = super(SignatureWorkflow, self).create(vals)
        
        # Si es un flujo con documentos locales, subirlos a Alfresco inmediatamente
        if workflow.document_source == 'local' and workflow.document_ids:
            workflow._upload_local_documents_to_alfresco()
        
        return workflow

    def _upload_local_documents_to_alfresco(self):
        """Sube documentos locales a la ruta específica en Alfresco"""
        self.ensure_one()
        
        if self.document_source != 'local':
            return
        
        try:
            # Crear carpeta del flujo en Alfresco
            workflow_folder = self._create_workflow_folder_in_alfresco()
            if not workflow_folder:
                raise UserError(_('No se pudo crear la carpeta del flujo en Alfresco'))
            
            uploaded_count = 0
            failed_count = 0
            
            # Subir cada documento local a la carpeta del flujo
            for doc in self.document_ids.filtered(lambda d: d.pdf_content and not d.alfresco_file_id):
                alfresco_file = self._upload_document_to_workflow_folder(doc, workflow_folder)
                if alfresco_file:
                    doc.write({
                        'alfresco_file_id': alfresco_file.id,
                        'download_url': f'/alfresco/file/{alfresco_file.id}/download'
                    })
                    uploaded_count += 1
                    _logger.info(f"Documento {doc.name} subido a Alfresco en carpeta del flujo")
                else:
                    failed_count += 1
                    _logger.error(f"Error subiendo documento {doc.name} a Alfresco")
            
            if uploaded_count == 0 and failed_count > 0:
                raise UserError(_('No se pudo subir ningún documento a Alfresco. Verifique la configuración.'))
            elif failed_count > 0:
                _logger.warning(f"Se subieron {uploaded_count} documentos exitosamente, {failed_count} fallaron")
            
            _logger.info(f"Documentos locales del flujo {self.id} subidos exitosamente a Alfresco ({uploaded_count}/{uploaded_count + failed_count})")
            
        except Exception as e:
            _logger.error(f"Error subiendo documentos locales del flujo {self.id}: {e}")
            raise UserError(_('Error subiendo documentos a Alfresco: %s') % str(e))

    def _create_workflow_folder_in_alfresco(self):
        """Crea la carpeta del flujo en la ruta /Sites/Flujos/<usuario>/<nombre_flujo>/"""
        self.ensure_one()
        
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            repo_id = config.get_param('asi_alfresco_integration.alfresco_repo_id', '-root-')
            
            if not all([url, user, pwd]):
                raise UserError(_('Configuración de Alfresco incompleta'))
            
            import requests
            import json
            
            # 1. Crear o encontrar carpeta Sites
            sites_folder = self._get_or_create_alfresco_folder('Sites', repo_id, None)
            if not sites_folder:
                raise UserError(_('No se pudo crear carpeta Sites'))
            
            # 2. Crear o encontrar carpeta Flujos
            flujos_folder = self._get_or_create_alfresco_folder('Flujos', sites_folder.node_id, sites_folder)
            if not flujos_folder:
                raise UserError(_('No se pudo crear carpeta Flujos'))
            
            # 3. Crear o encontrar carpeta del usuario
            user_folder_name = self.creator_id.login
            user_folder = self._get_or_create_alfresco_folder(user_folder_name, flujos_folder.node_id, flujos_folder)
            if not user_folder:
                raise UserError(_('No se pudo crear carpeta del usuario'))
            
            # 4. Crear carpeta específica del flujo
            workflow_folder_name = self.name
            workflow_folder = self._get_or_create_alfresco_folder(workflow_folder_name, user_folder.node_id, user_folder)
            if not workflow_folder:
                raise UserError(_('No se pudo crear carpeta del flujo'))
            
            # Actualizar el flujo con la carpeta creada
            self.write({'alfresco_folder_id': workflow_folder.id})
            
            _logger.info(f"Carpeta del flujo creada en: /Sites/Flujos/{user_folder_name}/{workflow_folder_name}/")
            return workflow_folder
            
        except Exception as e:
            _logger.error(f"Error creando carpeta del flujo en Alfresco: {e}")
            raise UserError(_('Error creando carpeta en Alfresco: %s') % str(e))

    def _get_or_create_alfresco_folder(self, folder_name, parent_node_id, parent_folder):
        """Obtiene o crea una carpeta en Alfresco"""
        try:
            # Buscar carpeta existente en Odoo
            existing_folder = self.env['alfresco.folder'].search([
                ('name', '=', folder_name),
                ('parent_id', '=', parent_folder.id if parent_folder else False)
            ], limit=1)
            
            if existing_folder:
                return existing_folder
            
            # Si no existe en Odoo, verificar si existe en Alfresco
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            import requests
            import json
            
            # Buscar carpeta en Alfresco
            search_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_node_id}/children"
            search_params = {
                'where': f"(nodeType='cm:folder' AND name='{folder_name}')",
                'maxItems': 1
            }
            
            search_response = requests.get(
                search_url,
                params=search_params,
                auth=(user, pwd),
                timeout=30
            )
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                if search_data.get('list', {}).get('entries'):
                    folder_info = search_data['list']['entries'][0]['entry']
                    existing_folder = self.env['alfresco.folder'].create({
                        'name': folder_name,
                        'node_id': folder_info['id'],
                        'parent_id': parent_folder.id if parent_folder else False,
                        'is_persistent': True,
                        'sync_status': 'synced',
                        'last_sync': fields.Datetime.now(),
                    })
                    _logger.info(f"Carpeta existente {folder_name} sincronizada desde Alfresco")
                    return existing_folder
            
            create_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_node_id}/children"
            folder_data = {
                "name": folder_name,
                "nodeType": "cm:folder",
                "properties": {
                    "cm:title": folder_name,
                    "cm:description": f"Carpeta para flujos de firma - {folder_name}"
                }
            }
            
            response = requests.post(
                create_url,
                json=folder_data,
                auth=(user, pwd),
                timeout=30
            )
            
            if response.status_code == 201:
                folder_info = response.json()['entry']
                
                # Crear registro en Odoo
                new_folder = self.env['alfresco.folder'].create({
                    'name': folder_name,
                    'node_id': folder_info['id'],
                    'parent_id': parent_folder.id if parent_folder else False,
                    'is_persistent': True,
                    'sync_status': 'synced',
                    'last_sync': fields.Datetime.now(),
                })
                
                _logger.info(f"Carpeta {folder_name} creada exitosamente en Alfresco")
                return new_folder
            elif response.status_code == 409:
                _logger.info(f"Carpeta {folder_name} ya existe en Alfresco (409), buscando...")
                
                # Buscar la carpeta que ya existe
                search_response_retry = requests.get(
                    search_url,
                    params=search_params,
                    auth=(user, pwd),
                    timeout=30
                )
                
                if search_response_retry.status_code == 200:
                    search_data_retry = search_response_retry.json()
                    if search_data_retry.get('list', {}).get('entries'):
                        folder_info = search_data_retry['list']['entries'][0]['entry']
                        existing_folder = self.env['alfresco.folder'].create({
                            'name': folder_name,
                            'node_id': folder_info['id'],
                            'parent_id': parent_folder.id if parent_folder else False,
                            'is_persistent': True,
                            'sync_status': 'synced',
                            'last_sync': fields.Datetime.now(),
                        })
                        _logger.info(f"Carpeta existente {folder_name} encontrada y sincronizada después de 409")
                        return existing_folder
                
                # Si no se puede encontrar después del 409, es un error real
                _logger.error(f"No se pudo encontrar carpeta {folder_name} después de error 409")
                return False
            else:
                _logger.error(f"Error creando carpeta {folder_name} en Alfresco: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            _logger.error(f"Error obteniendo/creando carpeta {folder_name}: {e}")
            return False

    def _upload_document_to_workflow_folder(self, document, workflow_folder):
        """Sube un documento a la carpeta del flujo en Alfresco"""
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            import requests
            import base64
            import json
            import uuid
            from datetime import datetime
            
            # Preparar datos del archivo
            pdf_data = base64.b64decode(document.pdf_content)
            
            upload_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{workflow_folder.node_id}/children"
            
            files = {
                'filedata': (document.name, pdf_data, 'application/pdf')
            }
            
            # Propiedades del documento
            properties = {
                'cm:title': document.name,
                'cm:description': f'Documento del flujo: {self.name}',
                'cm:author': self.creator_id.name,
                'asi:workflow_id': str(self.id),
                'asi:workflow_name': self.name,
                'asi:upload_date': fields.Datetime.now().isoformat()
            }
            
            data = {
                'name': document.name,
                'nodeType': 'cm:content',
                'properties': json.dumps(properties)
            }
            
            _logger.info(f"Subiendo documento {document.name} a carpeta {workflow_folder.node_id}")
            
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                auth=(user, pwd),
                timeout=60
            )
            
            _logger.info(f"Respuesta de Alfresco para {document.name}: Status {response.status_code}")
            
            if response.status_code in [201, 409]:  # 201 = creado, 409 = ya existe
                if response.status_code == 201:
                    try:
                        response_data = response.json()
                        _logger.info(f"Datos de respuesta completos para {document.name}: {response_data}")
                        
                        # Intentar obtener ID real de la respuesta
                        if 'entry' in response_data and response_data['entry'] and 'id' in response_data['entry']:
                            file_id = response_data['entry']['id']
                            _logger.info(f"ID real obtenido de respuesta: {file_id}")
                        else:
                            # Crear ID ficticio basado en información conocida
                            file_id = f"workflow-{self.id}-{document.name.replace(' ', '_').replace('.', '_')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            _logger.warning(f"Respuesta vacía de Alfresco, usando ID ficticio: {file_id}")
                    except:
                        # Si no se puede parsear la respuesta, crear ID ficticio
                        file_id = f"workflow-{self.id}-{document.name.replace(' ', '_').replace('.', '_')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        _logger.warning(f"Error parseando respuesta, usando ID ficticio: {file_id}")
                else:  # 409 - archivo ya existe
                    file_id = f"existing-{self.id}-{document.name.replace(' ', '_').replace('.', '_')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    _logger.info(f"Archivo ya existe (409), usando ID ficticio: {file_id}")
                
                # Crear registro en Odoo con ID (real o ficticio)
                alfresco_file = self.env['alfresco.file'].create({
                    'name': document.name,
                    'folder_id': workflow_folder.id,
                    'alfresco_node_id': file_id,
                    'mime_type': 'application/pdf',
                    'file_size': len(pdf_data),
                    'modified_at': fields.Datetime.now(),
                })
                
                _logger.info(f"Documento {document.name} procesado exitosamente con ID: {file_id} (Status: {response.status_code})")
                return alfresco_file
                
            else:
                _logger.error(f"Error subiendo documento {document.name}: {response.status_code} - {response.text}")
                try:
                    error_data = response.json()
                    _logger.error(f"Detalles del error: {error_data}")
                except:
                    _logger.error(f"No se pudo parsear respuesta de error como JSON")
                return False
                
        except Exception as e:
            _logger.error(f"Excepción subiendo documento {document.name}: {e}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def action_send_for_signature(self):
        """Envía el flujo para firma al usuario destinatario"""
        self.ensure_one()
        if not self.document_ids:
            raise UserError(_('Debe agregar al menos un documento al flujo.'))
        
        if self.document_source == 'local':
            local_docs_without_alfresco = self.document_ids.filtered(lambda d: not d.alfresco_file_id)
            if local_docs_without_alfresco:
                # Intentar subir documentos que no estén en Alfresco
                self._upload_local_documents_to_alfresco()
                local_docs_with_alfresco = self.document_ids.filtered(lambda d: d.alfresco_file_id)
                if not local_docs_with_alfresco:
                    raise UserError(_('No se pudo subir ningún documento a Alfresco. Verifique la configuración.'))
                elif len(local_docs_with_alfresco) < len(self.document_ids):
                    # Algunos documentos fallaron pero otros se subieron
                    failed_docs = self.document_ids.filtered(lambda d: not d.alfresco_file_id)
                    _logger.warning(f"Algunos documentos no se subieron: {failed_docs.mapped('name')}")
        
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now()
        })
        
        # Enviar notificación por email
        self._send_signature_request_notification()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Flujo enviado exitosamente a {self.target_user_id.name}',
                'type': 'success',
            }
        }

    def action_mark_as_completed(self):
        """Acción manual para marcar el flujo como completado"""
        self.ensure_one()
        
        if self.state not in ['signed', 'completed']:
            raise UserError(_('Solo se pueden completar flujos que estén firmados.'))
        
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Flujo marcado como completado',
                'type': 'success',
            }
        }

    def action_sign_documents(self):
        """Acción para que el usuario destinatario firme los documentos"""
        self.ensure_one()
        
        if self.env.user != self.target_user_id:
            raise UserError(_('Solo el usuario destinatario puede firmar estos documentos.'))
        
        if self.state != 'sent':
            raise UserError(_('Este flujo no está disponible para firma.'))
        
        return self._process_alfresco_signature()

    def _process_alfresco_signature(self):
        """Procesa la firma de documentos de Alfresco"""
        alfresco_files = self.document_ids.mapped('alfresco_file_id').filtered(lambda f: f)
        
        # Si no hay archivos de Alfresco asignados, intentar buscarlos por nombre en la carpeta del flujo
        if not alfresco_files and self.alfresco_folder_id:
            _logger.info(f"No se encontraron archivos de Alfresco asignados, buscando en carpeta {self.alfresco_folder_id.name}")
            
            # Buscar archivos PDF en la carpeta del flujo que coincidan con los nombres de los documentos
            document_names = self.document_ids.mapped('name')
            for doc_name in document_names:
                matching_files = self.env['alfresco.file'].search([
                    ('folder_id', '=', self.alfresco_folder_id.id),
                    ('name', '=', doc_name)
                ])
                if matching_files:
                    alfresco_files |= matching_files[0]  # Tomar el primero si hay múltiples
                    _logger.info(f"Encontrado archivo {doc_name} en Alfresco")
                    
                    # Actualizar el documento con el archivo encontrado
                    doc = self.document_ids.filtered(lambda d: d.name == doc_name)
                    if doc:
                        doc[0].write({'alfresco_file_id': matching_files[0].id})
        
        # Si aún no hay archivos, buscar todos los PDFs en la carpeta del flujo
        if not alfresco_files and self.alfresco_folder_id:
            _logger.info(f"Buscando todos los archivos PDF en carpeta del flujo {self.alfresco_folder_id.name}")
            all_pdf_files = self.env['alfresco.file'].search([
                ('folder_id', '=', self.alfresco_folder_id.id),
                ('name', 'ilike', '%.pdf')
            ])
            
            if all_pdf_files:
                alfresco_files = all_pdf_files
                _logger.info(f"Encontrados {len(all_pdf_files)} archivos PDF en la carpeta del flujo")
                
                # Intentar asociar archivos con documentos por nombre
                for doc in self.document_ids.filtered(lambda d: not d.alfresco_file_id):
                    matching_file = all_pdf_files.filtered(lambda f: f.name == doc.name)
                    if matching_file:
                        doc.write({'alfresco_file_id': matching_file[0].id})
        
        if not alfresco_files:
            error_msg = f'No hay archivos de Alfresco disponibles para firmar.'
            if self.alfresco_folder_id:
                error_msg += f' Carpeta del flujo: {self.alfresco_folder_id.name}'
            else:
                error_msg += ' No se encontró carpeta del flujo en Alfresco.'
            
            _logger.warning(error_msg)
            raise UserError(_(error_msg))
        
        _logger.info(f"Procesando firma de {len(alfresco_files)} archivos de Alfresco")
        
        # Crear wizard de firma de Alfresco
        wizard = self.env['alfresco.firma.wizard'].create({
            'file_ids': [(6, 0, alfresco_files.ids)],
            'signature_role': self.signature_role_id.id,
            'signature_position': self.signature_position,
            'from_workflow': True,
            'workflow_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Firmar Documentos del Flujo',
            'res_model': 'alfresco.firma.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'workflow_id': self.id,
                'from_workflow': True,
            }
        }

    def action_mark_as_signed(self):
        """Marca el flujo como firmado y procesa los documentos firmados"""
        self.ensure_one()
        
        self.write({
            'state': 'signed',
            'signed_date': fields.Datetime.now()
        })
        
        try:
            self._process_signed_documents()
            
            # Marcar como completado automáticamente
            self.write({
                'state': 'completed',
                'completed_date': fields.Datetime.now()
            })
            
            # Notificar al creador
            self._send_completion_notification()
            
            _logger.info(f"Flujo {self.id} completado automáticamente después de firmar todos los documentos")
            
        except Exception as e:
            _logger.error(f"Error procesando documentos firmados del flujo {self.id}: {e}")
            # Mantener estado 'signed' si hay error en el procesamiento
            self.write({
                'signature_notes': f'Error procesando documentos: {str(e)}'
            })

    def _process_signed_documents(self):
        """Procesa documentos firmados actualizando URLs de descarga"""
        # Todos los documentos ahora están en Alfresco, actualizar URLs
        for doc in self.document_ids:
            if doc.alfresco_file_id:
                doc.write({
                    'download_url': f'/alfresco/file/{doc.alfresco_file_id.id}/download',
                    'is_signed': True,
                    'signed_date': fields.Datetime.now()
                })

    def get_signed_documents_download_urls(self):
        """Obtiene las URLs de descarga de todos los documentos firmados"""
        self.ensure_one()
        urls = []
        
        for doc in self.document_ids.filtered('is_signed'):
            if doc.alfresco_file_id:
                # Para documentos de Alfresco, usar la URL directa del archivo
                download_url = f"/alfresco/file/{doc.alfresco_file_id.id}/download"
            else:
                # Fallback para documentos sin archivo de Alfresco
                download_url = f"/signature_workflow/document/{doc.id}/download"
            
            full_url = f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}{download_url}"
            urls.append({
                'name': doc.name,
                'url': full_url,
                'signed_date': doc.signed_date
            })
        
        return urls

    def _send_completion_notification(self):
        """Envía notificación de finalización al creador"""
        self.ensure_one()
        
        try:
            # Enviar email usando template
            template = self.env.ref('asi_signature_workflow.mail_template_signature_completed', raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=True)
                _logger.info(f"Notificación de finalización enviada para flujo {self.id}")
            
            # Crear notificación interna en Odoo
            download_urls = self.get_signed_documents_download_urls()
            urls_text = '\n'.join([f'• {doc["name"]}: {doc["url"]}' for doc in download_urls])
            
            self.env['mail.message'].create({
                'subject': f'Documentos Firmados: {self.name}',
                'body': f'''
                <p>Su flujo de firma digital ha sido completado exitosamente:</p>
                <ul>
                    <li><strong>Flujo:</strong> {self.name}</li>
                    <li><strong>Firmado por:</strong> {self.target_user_id.name}</li>
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s) firmados</li>
                    <li><strong>Fecha:</strong> {self.completed_date}</li>
                    <li><strong>Carpeta Alfresco:</strong> /Sites/Flujos/{self.creator_id.login}/{self.name}/</li>
                </ul>
                <p><strong>URLs de descarga individual:</strong></p>
                <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 12px;">
                    {urls_text.replace(chr(10), '<br/>')}
                </div>
                <p style="text-align: center; margin: 20px 0;">
                    <a href="/signature_workflow/download_signed/{self.id}" 
                       style="background-color: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        📥 DESCARGAR AHORA!
                    </a>
                </p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, self.creator_id.partner_id.id)],
                'author_id': self.env.user.partner_id.id,
            })
            
            # Marcar actividad como completada si existe
            activities = self.env['mail.activity'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('user_id', '=', self.target_user_id.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id)
            ])
            
            if activities:
                activities.action_done()
            
            # Crear nueva actividad para el creador
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_call').id,
                'summary': f'Documentos firmados disponibles: {self.name}',
                'note': f'''
                <p>Los documentos del flujo han sido firmados y están listos para descarga individual.</p>
                <p><strong>Firmado por:</strong> {self.target_user_id.name}</p>
                <p><strong>Documentos:</strong> {self.document_count} archivo(s)</p>
                <p><a href="/signature_workflow/download_signed/{self.id}">Acceder a página de descarga</a></p>
                ''',
                'res_model_id': self.env['ir.model']._get(self._name).id,
                'res_id': self.id,
                'user_id': self.creator_id.id,
                'date_deadline': fields.Date.today(),
            })
            
        except Exception as e:
            _logger.error(f"Error enviando notificación de finalización: {e}")

    def action_send_reminder(self):
        """Envía recordatorio al usuario destinatario"""
        self.ensure_one()
        
        if self.state != 'sent':
            raise UserError(_('Solo se pueden enviar recordatorios para flujos enviados.'))
        
        try:
            # Crear mensaje de recordatorio
            self.env['mail.message'].create({
                'subject': f'Recordatorio: Firma Pendiente - {self.name}',
                'body': f'''
                <p><strong>Recordatorio:</strong> Tiene pendiente la firma de documentos.</p>
                <ul>
                    <li><strong>Flujo:</strong> {self.name}</li>
                    <li><strong>Enviado:</strong> {self.sent_date}</li>
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s)</li>
                </ul>
                <p>Por favor, acceda al sistema para completar la firma.</p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, self.target_user_id.partner_id.id)],
                'author_id': self.creator_id.partner_id.id,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Recordatorio enviado a {self.target_user_id.name}',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Error enviando recordatorio: {e}")
            raise UserError(_('Error enviando recordatorio: %s') % str(e))

    def action_download_all_signed(self):
        """Descarga todos los documentos firmados del flujo"""
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_('El flujo debe estar completado para descargar los documentos firmados.'))
        
        signed_docs = self.document_ids.filtered('is_signed')
        if not signed_docs:
            raise UserError(_('No hay documentos firmados disponibles para descarga.'))
        
        # Si solo hay un documento, descargarlo directamente
        if len(signed_docs) == 1:
            return signed_docs.action_download_document()
        
        # Si hay múltiples documentos, redirigir a página de descarga
        return {
            'type': 'ir.actions.act_url',
            'url': f'/signature_workflow/download_signed/{self.id}',
            'target': 'new',
        }

    def _send_signature_request_notification(self):
        """Envía notificación de solicitud de firma por email"""
        self.ensure_one()
    
        try:
            # Enviar email usando template
            template = self.env.ref('asi_signature_workflow.mail_template_signature_request')
            if template:
                template.send_mail(self.id, force_send=True)
                _logger.info(f"Notificación de solicitud de firma enviada para flujo {self.id}")

            # Crear notificación interna en Odoo
            self.env['mail.message'].create({
                'subject': f'Solicitud de Firma: {self.name}',
                'body': f'''
                <p>Se ha enviado una solicitud de firma digital a <strong>{self.target_user_id.name}</strong>.</p>
                <ul>
                    <li><strong>Flujo:</strong> {self.name}</li>
                    <li><strong>Destinatario:</strong> {self.target_user_id.name}</li>
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s) PDF</li>
                    <li><strong>Rol de firma:</strong> {self.signature_role_id.name}</li>
                </ul>
                <p>El destinatario recibirá una notificación por correo electrónico.</p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, self.target_user_id.partner_id.id)],
                'author_id': self.creator_id.partner_id.id,
            })

            # Crear actividad para el usuario destinatario
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': f'Solicitud de Firma Digital: {self.name}',
                'note': f'''
                <p>Tiene pendiente la firma de documentos digitales:</p>
                <ul>
                    <li><strong>Flujo:</strong> {self.name}</li>
                    <li><strong>Enviado por:</strong> {self.creator_id.name}</li>
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s) PDF</li>
                    <li><strong>Rol de firma:</strong> {self.signature_role_id.name}</li>
                </ul>
                <p>Por favor, acceda al sistema para completar la firma.</p>
                ''',
                'res_model_id': self.env['ir.model']._get(self._name).id,
                'res_id': self.id,
                'user_id': self.target_user_id.id,
                'date_deadline': fields.Date.today() + timedelta(days=3),  # 3 días para firmar
            })
        
        except Exception as e:
            _logger.error(f"Error enviando notificación de solicitud de firma: {e}")
            raise UserError(_('Error enviando notificación: %s') % str(e))    

    def _get_signed_local_wizard(self):
        """Obtiene el wizard de firma local asociado a este flujo"""
        if not self.sent_date:
            _logger.warning(f"Flujo {self.id} no tiene fecha de envío")
            return False
            
        # Buscar wizard de firma que tenga el contexto de este workflow
        recent_wizards = self.env['firma.documento.wizard'].search([
            ('create_date', '>=', self.sent_date),
            ('create_uid', '=', self.target_user_id.id),
            ('from_workflow', '=', True),
            ('workflow_id', '=', self.id)
        ], order='create_date desc', limit=1)
        
        if recent_wizards:
            return recent_wizards[0]
        
        # Fallback: buscar por coincidencia de nombres de documentos
        fallback_wizards = self.env['firma.documento.wizard'].search([
            ('create_date', '>=', self.sent_date),
            ('create_uid', '=', self.target_user_id.id)
        ], order='create_date desc', limit=5)
        
        for wizard in fallback_wizards:
            wizard_doc_names = set(wizard.document_ids.mapped('document_name'))
            workflow_doc_names = set(self.document_ids.mapped('name'))
            
            if wizard_doc_names == workflow_doc_names:
                _logger.info(f"Encontrado wizard {wizard.id} por coincidencia de nombres para flujo {self.id}")
                return wizard
        
        _logger.warning(f"No se encontró wizard de firma para el flujo {self.id}")
        return False

class SignatureWorkflowDocument(models.Model):
    _name = 'signature.workflow.document'
    _description = 'Documento del Flujo de Firma'

    workflow_id = fields.Many2one('signature.workflow', string='Flujo', required=True, ondelete='cascade')
    name = fields.Char(string='Nombre del Documento', required=True)
    
    # Para documentos locales
    pdf_content = fields.Binary(string='Contenido PDF')
    pdf_filename = fields.Char(string='Nombre del Archivo')
    
    # Para documentos de Alfresco (ahora todos los documentos tendrán esto)
    alfresco_file_id = fields.Many2one('alfresco.file', string='Archivo de Alfresco')
    
    # URL de descarga después de firmado
    download_url = fields.Char(string='URL de Descarga')
    
    # Estado del documento
    is_signed = fields.Boolean(string='Firmado', default=False)
    signed_date = fields.Datetime(string='Fecha de Firma')

    def action_download_document(self):
        """Descarga el documento firmado"""
        self.ensure_one()
        
        if not self.is_signed:
            raise UserError(_('El documento no está firmado aún.'))
        
        if not self.download_url:
            raise UserError(_('No hay URL de descarga disponible para este documento.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': self.download_url,
            'target': 'self',
        }
