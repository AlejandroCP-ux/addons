from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class AlfrescoExplorer(models.Model):
    """Modelo virtual para mostrar carpetas y archivos juntos"""
    _name = 'alfresco.explorer'
    _description = 'Explorador Unificado de Alfresco'
    _auto = False  # No crear tabla en BD
    _order = 'item_type desc, name'  # Carpetas primero, luego archivos

    # Campos comunes
    name = fields.Char(string="Nombre")
    item_type = fields.Selection([
        ('folder', 'Carpeta'),
        ('file', 'Archivo PDF')
    ], string="Tipo")
    parent_folder_id = fields.Many2one('alfresco.folder', string="Carpeta Padre")
    size_human = fields.Char(string="Tamaño")
    modified_at = fields.Datetime(string="Modificado")
    
    # Campos específicos para identificar el registro real
    folder_id = fields.Many2one('alfresco.folder', string="Carpeta")
    file_id = fields.Many2one('alfresco.file', string="Archivo")
    
    # Campos para iconos y acciones
    icon = fields.Char(string="Icono", compute='_compute_icon')
    action_label = fields.Char(string="Acción", compute='_compute_action_label')

    @api.depends('item_type')
    def _compute_icon(self):
        for record in self:
            if record.item_type == 'folder':
                record.icon = 'fa-folder'
            else:
                record.icon = 'fa-file-pdf-o'

    @api.depends('item_type')
    def _compute_action_label(self):
        for record in self:
            if record.item_type == 'folder':
                record.action_label = 'Abrir'
            else:
                record.action_label = 'Preview'

    def init(self):
        """No crear tabla física"""
        pass

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Implementar búsqueda personalizada"""
        if domain is None:
            domain = []
        
        # Buscar parent_folder_id en el dominio
        parent_folder_id = False
        for condition in domain:
            if isinstance(condition, (list, tuple)) and len(condition) == 3:
                if condition[0] == 'parent_folder_id' and condition[1] == '=':
                    parent_folder_id = condition[2]
                    break
        
        results = []
        
        # Obtener carpetas hijas
        folder_domain = [('parent_id', '=', parent_folder_id)]
        folders = self.env['alfresco.folder'].search(folder_domain)
        
        for folder in folders:
            results.append({
                'id': f"folder_{folder.id}",
                'name': folder.name,
                'item_type': 'folder',
                'parent_folder_id': parent_folder_id,
                'size_human': f"{folder.subfolder_count} subcarpetas, {folder.file_count} archivos",
                'modified_at': folder.external_modified,
                'folder_id': folder.id,
                'file_id': False,
                'icon': 'fa-folder',
                'action_label': 'Abrir',
            })
        
        # Obtener archivos de la carpeta actual
        if parent_folder_id:
            file_domain = [('folder_id', '=', parent_folder_id)]
            files = self.env['alfresco.file'].search(file_domain)
            
            for file_rec in files:
                results.append({
                    'id': f"file_{file_rec.id}",
                    'name': file_rec.name,
                    'item_type': 'file',
                    'parent_folder_id': parent_folder_id,
                    'size_human': file_rec.file_size_human,
                    'modified_at': file_rec.modified_at,
                    'folder_id': False,
                    'file_id': file_rec.id,
                    'icon': 'fa-file-pdf-o',
                    'action_label': 'Preview',
                })
        
        # Aplicar orden
        if order:
            reverse = 'desc' in order.lower()
            if 'item_type' in order:
                results.sort(key=lambda x: x['item_type'], reverse=reverse)
            elif 'name' in order:
                results.sort(key=lambda x: x['name'], reverse=reverse)
        
        # Aplicar paginación
        if offset:
            results = results[offset:]
        if limit:
            results = results[:limit]
        
        return results

    @api.model
    def search_count(self, domain=None):
        """Contar registros"""
        if domain is None:
            domain = []
        
        parent_folder_id = False
        for condition in domain:
            if isinstance(condition, (list, tuple)) and len(condition) == 3:
                if condition[0] == 'parent_folder_id' and condition[1] == '=':
                    parent_folder_id = condition[2]
                    break
        
        folder_count = self.env['alfresco.folder'].search_count([('parent_id', '=', parent_folder_id)])
        file_count = 0
        if parent_folder_id:
            file_count = self.env['alfresco.file'].search_count([('folder_id', '=', parent_folder_id)])
        
        return folder_count + file_count

    def action_open_item(self):
        """Acción para abrir carpeta o archivo"""
        self.ensure_one()
        
        # Obtener el ID real del string
        if self.id.startswith('folder_'):
            folder_id = int(self.id.replace('folder_', ''))
            folder = self.env['alfresco.folder'].browse(folder_id)
            return folder.action_open_folder()
        
        elif self.id.startswith('file_'):
            file_id = int(self.id.replace('file_', ''))
            file_rec = self.env['alfresco.file'].browse(file_id)
            return file_rec.action_preview_file()
        
        return False

    def action_download_file(self):
        """Acción para descargar archivo"""
        self.ensure_one()
        
        if self.id.startswith('file_'):
            file_id = int(self.id.replace('file_', ''))
            file_rec = self.env['alfresco.file'].browse(file_id)
            return file_rec.action_download_file()
        
        return False

    def action_sync_folder(self):
        """Acción para sincronizar carpeta"""
        self.ensure_one()
        
        if self.id.startswith('folder_'):
            folder_id = int(self.id.replace('folder_', ''))
            folder = self.env['alfresco.folder'].browse(folder_id)
            return folder.action_sync_folder()
        
        return False
