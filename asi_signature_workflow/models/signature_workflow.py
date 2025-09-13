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
    ], string='Estado', default='draft', required=True)
    
    # Documentos del flujo
    document_ids = fields.One2many('signature.workflow.document', 'workflow_id', string='Documentos')
    document_count = fields.Integer(string='Cantidad de Documentos', compute='_compute_document_count')
    
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

    def action_send_for_signature(self):
        """Envía el flujo para firma al usuario destinatario"""
        self.ensure_one()
        if not self.document_ids:
            raise UserError(_('Debe agregar al menos un documento al flujo.'))
        
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

    def action_sign_documents(self):
        """Acción para que el usuario destinatario firme los documentos"""
        self.ensure_one()
        
        if self.env.user != self.target_user_id:
            raise UserError(_('Solo el usuario destinatario puede firmar estos documentos.'))
        
        if self.state != 'sent':
            raise UserError(_('Este flujo no está disponible para firma.'))
        
        # Procesar firma según el tipo de documento
        if self.document_source == 'alfresco':
            return self._process_alfresco_signature()
        else:
            return self._process_local_signature()

    def _process_alfresco_signature(self):
        """Procesa la firma de documentos de Alfresco"""
        alfresco_files = self.document_ids.mapped('alfresco_file_id')
        
        # Crear wizard de firma de Alfresco
        wizard = self.env['alfresco.firma.wizard'].create({
            'file_ids': [(6, 0, alfresco_files.ids)],
            'signature_role': self.signature_role_id.id,
            'signature_position': self.signature_position,
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

    def _process_local_signature(self):
        """Procesa la firma de documentos locales"""
        # Crear documentos temporales para el wizard de firma local
        document_lines = []
        for doc in self.document_ids:
            document_lines.append((0, 0, {
                'document_name': doc.name,
                'pdf_document': doc.pdf_content,
            }))
        
        # Crear wizard de firma local
        wizard = self.env['firma.documento.wizard'].create({
            'document_ids': document_lines,
            'signature_role': self.signature_role_id.id,
            'signature_position': self.signature_position,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Firmar Documentos del Flujo',
            'res_model': 'firma.documento.wizard',
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
        
        # Procesar documentos firmados según el origen
        if self.document_source == 'alfresco':
            self._process_signed_alfresco_documents()
        else:
            self._process_signed_local_documents()
        
        # Marcar como completado
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now()
        })
        
        # Notificar al creador
        self._send_completion_notification()

    def _process_signed_alfresco_documents(self):
        """Procesa documentos firmados de Alfresco (ya están actualizados como nuevas versiones)"""
        # Los documentos de Alfresco ya se actualizan automáticamente como nuevas versiones
        # Solo necesitamos actualizar las URLs de descarga
        for doc in self.document_ids:
            if doc.alfresco_file_id:
                doc.write({
                    'download_url': f'/alfresco/file/{doc.alfresco_file_id.id}/download',
                    'is_signed': True,
                    'signed_date': fields.Datetime.now()
                })

    def _process_signed_local_documents(self):
        """Procesa documentos locales firmados subiéndolos a una carpeta compartida"""
        # Crear o encontrar carpeta compartida para el creador
        shared_folder = self._get_or_create_shared_folder()
        
        if not shared_folder:
            _logger.warning(f"No se pudo crear carpeta compartida para el flujo {self.id}")
            return
        
        # Obtener documentos firmados del wizard de firma local
        signed_wizard = self._get_signed_local_wizard()
        if not signed_wizard:
            _logger.warning(f"No se encontró wizard de firma para el flujo {self.id}")
            return
        
        # Subir cada documento firmado a Alfresco
        for doc in self.document_ids:
            signed_doc = signed_wizard.document_ids.filtered(lambda d: d.document_name == doc.name)
            if signed_doc and signed_doc.pdf_signed:
                alfresco_file = self._upload_signed_document_to_alfresco(
                    doc, signed_doc.pdf_signed, shared_folder
                )
                if alfresco_file:
                    doc.write({
                        'download_url': f'/alfresco/file/{alfresco_file.id}/download',
                        'is_signed': True,
                        'signed_date': fields.Datetime.now()
                    })

    def _get_or_create_shared_folder(self):
        """Obtiene o crea la carpeta compartida del creador en Alfresco"""
        folder_name = f"Documentos_Firmados_{self.creator_id.login}"
        
        # Buscar carpeta existente
        existing_folder = self.env['alfresco.folder'].search([
            ('name', '=', folder_name),
            ('parent_id', '=', False)  # En la raíz
        ], limit=1)
        
        if existing_folder:
            return existing_folder
        
        # Crear nueva carpeta en Alfresco
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            repo_id = config.get_param('asi_alfresco_integration.alfresco_repo_id', '-root-')
            
            if not all([url, user, pwd]):
                _logger.error("Configuración de Alfresco incompleta")
                return False
            
            import requests
            
            # Crear carpeta en Alfresco
            create_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{repo_id}/children"
            folder_data = {
                "name": folder_name,
                "nodeType": "cm:folder",
                "properties": {
                    "cm:title": f"Documentos Firmados - {self.creator_id.name}",
                    "cm:description": "Carpeta para documentos firmados mediante flujos de trabajo"
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
                    'parent_id': False,
                    'is_persistent': True,
                })
                
                _logger.info(f"Carpeta compartida creada: {folder_name}")
                return new_folder
            else:
                _logger.error(f"Error creando carpeta en Alfresco: {response.status_code}")
                return False
                
        except Exception as e:
            _logger.error(f"Error creando carpeta compartida: {e}")
            return False

    def _get_signed_local_wizard(self):
        """Obtiene el wizard de firma local asociado a este flujo"""
        # Buscar wizard de firma que tenga el contexto de este workflow
        # Esto es una aproximación, en un caso real se necesitaría un mecanismo más robusto
        recent_wizards = self.env['firma.documento.wizard'].search([
            ('create_date', '>=', self.sent_date),
            ('create_uid', '=', self.target_user_id.id)
        ], order='create_date desc', limit=5)
        
        # Buscar el wizard que tenga documentos con nombres coincidentes
        for wizard in recent_wizards:
            wizard_doc_names = set(wizard.document_ids.mapped('document_name'))
            workflow_doc_names = set(self.document_ids.mapped('name'))
            
            if wizard_doc_names == workflow_doc_names:
                return wizard
        
        return False

    def _upload_signed_document_to_alfresco(self, workflow_doc, signed_pdf_content, target_folder):
        """Sube un documento firmado a Alfresco"""
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            import requests
            import base64
            
            # Preparar nombre del archivo firmado
            original_name = workflow_doc.name
            if not original_name.lower().endswith('_firmado.pdf'):
                name_parts = original_name.rsplit('.', 1)
                if len(name_parts) == 2:
                    signed_name = f"{name_parts[0]}_firmado.{name_parts[1]}"
                else:
                    signed_name = f"{original_name}_firmado.pdf"
            else:
                signed_name = original_name
            
            # Subir archivo a Alfresco
            upload_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{target_folder.node_id}/children"
            
            pdf_data = base64.b64decode(signed_pdf_content)
            
            files = {
                'filedata': (signed_name, pdf_data, 'application/pdf')
            }
            
            data = {
                'name': signed_name,
                'nodeType': 'cm:content',
                'properties': {
                    'cm:title': f'Documento firmado - {original_name}',
                    'cm:description': f'Documento firmado mediante flujo de trabajo ID: {self.id}'
                }
            }
            
            response = requests.post(
                upload_url,
                files=files,
                data={'properties': str(data)},
                auth=(user, pwd),
                timeout=60
            )
            
            if response.status_code == 201:
                file_info = response.json()['entry']
                
                # Crear registro en Odoo
                alfresco_file = self.env['alfresco.file'].create({
                    'name': signed_name,
                    'folder_id': target_folder.id,
                    'alfresco_node_id': file_info['id'],
                    'mime_type': 'application/pdf',
                    'file_size': len(pdf_data),
                    'modified_at': fields.Datetime.now(),
                })
                
                _logger.info(f"Documento firmado subido a Alfresco: {signed_name}")
                return alfresco_file
            else:
                _logger.error(f"Error subiendo documento a Alfresco: {response.status_code}")
                return False
                
        except Exception as e:
            _logger.error(f"Error subiendo documento firmado: {e}")
            return False

    def get_signed_documents_download_urls(self):
        """Obtiene las URLs de descarga de todos los documentos firmados"""
        self.ensure_one()
        urls = []
        
        for doc in self.document_ids.filtered('is_signed'):
            download_url = f"/signature_workflow/document/{doc.id}/download"
            full_url = f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}{download_url}"
            urls.append({
                'name': doc.name,
                'url': full_url
            })
        
        return urls

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

    def _send_completion_notification(self):
        """Envía notificación de finalización al creador"""
        self.ensure_one()
        
        try:
            # Enviar email usando template
            template = self.env.ref('asi_signature_workflow.mail_template_signature_completed')
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
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s)</li>
                    <li><strong>Fecha de envío:</strong> {self.sent_date}</li>
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

class SignatureWorkflowDocument(models.Model):
    _name = 'signature.workflow.document'
    _description = 'Documento del Flujo de Firma'

    workflow_id = fields.Many2one('signature.workflow', string='Flujo', required=True, ondelete='cascade')
    name = fields.Char(string='Nombre del Documento', required=True)
    
    # Para documentos locales
    pdf_content = fields.Binary(string='Contenido PDF')
    pdf_filename = fields.Char(string='Nombre del Archivo')
    
    # Para documentos de Alfresco
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