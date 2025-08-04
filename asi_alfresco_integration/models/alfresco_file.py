from odoo import models, fields, api
import requests
import logging
import base64

_logger = logging.getLogger(__name__)

class AlfrescoFile(models.Model):
    _name = 'alfresco.file'
    _description = 'Archivo importado desde Alfresco'

    name = fields.Char(string="Nombre del archivo", required=True)
    folder_id = fields.Many2one('alfresco.folder', string="Carpeta", ondelete='cascade')
    alfresco_node_id = fields.Char(string="ID de nodo en Alfresco", readonly=True, required=True, index=True)
    mime_type = fields.Char(string="MIME Type")
    file_size = fields.Integer(string="Tamaño (bytes)")
    file_size_human = fields.Char(string="Tamaño", compute='_compute_file_size_human')
    modified_at = fields.Datetime(string="Modificado en Alfresco")
    content_url = fields.Char(string="URL de contenido", compute='_compute_content_url')
    preview_url = fields.Char(string="URL de preview", compute='_compute_preview_url')
    
    # Campo para almacenar el contenido del PDF temporalmente para preview
    pdf_content = fields.Binary(string="Contenido PDF", attachment=True)
    pdf_filename = fields.Char(string="Nombre archivo PDF")



    def _get_config_param(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)

    @api.depends('file_size')
    def _compute_file_size_human(self):
        for record in self:
            if record.file_size:
                if record.file_size < 1024:
                    record.file_size_human = f"{record.file_size} B"
                elif record.file_size < 1024 * 1024:
                    record.file_size_human = f"{round(record.file_size / 1024, 1)} KB"
                else:
                    record.file_size_human = f"{round(record.file_size / (1024 * 1024), 1)} MB"
            else:
                record.file_size_human = "0 B"

    @api.depends('alfresco_node_id')
    def _compute_content_url(self):
        """Genera la URL para descargar el contenido del archivo"""
        
        base_url = self._get_config_param('asi_alfresco_integration.alfresco_server_url')
        
        for record in self:
            if record.alfresco_node_id and base_url:
                record.content_url = f"{base_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{record.alfresco_node_id}/content"
            else:
                record.content_url = False

    @api.depends('alfresco_node_id')
    def _compute_preview_url(self):
        """Genera la URL para el preview del PDF"""
        for record in self:
            if record.alfresco_node_id:
                record.preview_url = f'/alfresco/file/{record.id}/preview'
            else:
                record.preview_url = False

    def action_delete_from_alfresco(self):
        """
        NUEVO: Método específico para eliminar archivo de Alfresco SOLO cuando el usuario lo solicite manualmente
        """
        self.ensure_one()
        
        url = self._get_config_param('asi_alfresco_integration.alfresco_server_url')
        user = self._get_config_param('asi_alfresco_integration.alfresco_username')
        pwd = self._get_config_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd, self.alfresco_node_id]):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Error: Configuración de Alfresco incompleta',
                    'type': 'danger',
                }
            }
        
        try:
            # Eliminar archivo de Alfresco usando la API REST
            delete_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{self.alfresco_node_id}"
            response = requests.delete(delete_url, auth=(user, pwd), timeout=30)
        
            if response.status_code == 200:
                _logger.info(f"Archivo {self.name} eliminado exitosamente de Alfresco")
                # Ahora eliminar el registro de Odoo
                super(AlfrescoFile, self).unlink()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'Archivo {self.name} eliminado correctamente de Alfresco y Odoo',
                        'type': 'success',
                    }
                }
            elif response.status_code == 404:
                _logger.warning(f"Archivo {self.name} no encontrado en Alfresco (ya eliminado)")
                # Eliminar solo de Odoo
                super(AlfrescoFile, self).unlink()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'Archivo {self.name} no existía en Alfresco, eliminado solo de Odoo',
                        'type': 'warning',
                    }
                }
            else:
                response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error eliminando archivo {self.name} de Alfresco: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error eliminando archivo de Alfresco: {str(e)}',
                    'type': 'danger',
                }
            }

    def action_download_file(self):
        """Descarga el contenido del archivo desde Alfresco"""
        self.ensure_one()
        
        url = self._get_config_param('asi_alfresco_integration.alfresco_server_url')
        user = self._get_config_param('asi_alfresco_integration.alfresco_username')
        pwd = self._get_config_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd, self.alfresco_node_id]):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Error: Configuración de Alfresco incompleta',
                    'type': 'danger',
                }
            }
        
        try:
            download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{self.alfresco_node_id}/content"
            response = requests.get(download_url, auth=(user, pwd), timeout=30)
            response.raise_for_status()
        
            return {
                'type': 'ir.actions.act_url',
                'url': f'/alfresco/file/{self.id}/download',
                'target': 'new',
            }
        
        except Exception as e:
            _logger.error("Error descargando archivo %s: %s", self.name, e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error descargando archivo: {str(e)}',
                    'type': 'danger',
                }
            }

    def action_preview_file(self):
        """Carga el PDF y abre la vista form con preview integrado"""
        self.ensure_one()
        
        # Primero cargar el contenido del PDF
        url = self._get_config_param('asi_alfresco_integration.alfresco_server_url')
        user = self._get_config_param('asi_alfresco_integration.alfresco_username')
        pwd = self._get_config_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd, self.alfresco_node_id]):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Error: Configuración de Alfresco incompleta',
                    'type': 'danger',
                }
            }
        
        try:
            download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{self.alfresco_node_id}/content"
            response = requests.get(download_url, auth=(user, pwd), timeout=30)
            response.raise_for_status()
        
            # Guardar el contenido en el campo binary
            self.write({
                'pdf_content': base64.b64encode(response.content),
                'pdf_filename': self.name,
            })
        
            # Abrir la vista form con el PDF cargado
            return {
                'type': 'ir.actions.act_window',
                'name': f'Preview: {self.name}',
                'res_model': 'alfresco.file',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'show_pdf_preview': True}
            }
        
        except Exception as e:
            _logger.error("Error cargando preview de archivo %s: %s", self.name, e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error cargando preview: {str(e)}',
                    'type': 'danger',
                }
            }

    def action_load_preview(self):
        """Carga el contenido del PDF para preview en Odoo"""
        self.ensure_one()
        
        url = self._get_config_param('asi_alfresco_integration.alfresco_server_url')
        user = self._get_config_param('asi_alfresco_integration.alfresco_username')
        pwd = self._get_config_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd, self.alfresco_node_id]):
            return False
        
        try:
            download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{self.alfresco_node_id}/content"
            response = requests.get(download_url, auth=(user, pwd), timeout=30)
            response.raise_for_status()
            
            # Guardar el contenido en el campo binary
            self.write({
                'pdf_content': base64.b64encode(response.content),
                'pdf_filename': self.name,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'PDF cargado correctamente para preview',
                    'type': 'success',
                }
            }
        
        except Exception as e:
            _logger.error("Error cargando preview de archivo %s: %s", self.name, e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error cargando preview: {str(e)}',
                    'type': 'danger',
                }
            }

    def action_open_firma_wizard(self):
        """Abre el wizard de firma para este archivo o archivos seleccionados"""
        # Obtener archivos seleccionados del contexto o usar el actual
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            active_ids = [self.id]

        # Verificar que los archivos existen y son válidos
        try:
            valid_files = self.env['alfresco.file'].browse(active_ids).exists().filtered(
                lambda f: f.name.lower().endswith('.pdf') and f.alfresco_node_id
            )
        except Exception as e:
            _logger.error("Error verificando archivos: %s", e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Error: Los archivos seleccionados no son válidos o no existen.',
                    'type': 'danger',
                }
            }

        if not valid_files:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No hay archivos PDF válidos seleccionados para firmar.',
                    'type': 'warning',
                }
            }

        # Crear el wizard con los archivos válidos
        wizard_vals = {
            'posicion_firma': 'derecha',  # Valor por defecto
        }

        try:
            wizard = self.env['alfresco.firma.wizard'].create(wizard_vals)
            # Asignar archivos después de crear el wizard
            wizard.write({'file_ids': [(6, 0, valid_files.ids)]})
    
            return {
                'type': 'ir.actions.act_window',
                'name': 'Firmar PDFs de Alfresco',
                'res_model': 'alfresco.firma.wizard',
                'res_id': wizard.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_file_ids': valid_files.ids,
                }
            }
        except Exception as e:
            _logger.error("Error creando wizard de firma: %s", e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error al abrir el wizard de firma: {str(e)}',
                    'type': 'danger',
                }
            }
