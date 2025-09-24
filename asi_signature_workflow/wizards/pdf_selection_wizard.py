# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import logging

_logger = logging.getLogger(__name__)

class PdfSelectionWizard(models.TransientModel):
    _name = 'pdf.selection.wizard'
    _description = 'Asistente para Selección de Documentos PDF'

    workflow_wizard_id = fields.Many2one('signature.workflow.wizard', string='Wizard Principal', 
                                       required=True, ondelete='cascade')
    selection_type = fields.Selection([
        ('local', 'Documentos Locales'),
        ('alfresco', 'Documentos de Alfresco')
    ], string='Tipo de Selección', required=True)
    
    # Para documentos locales
    local_document_ids = fields.One2many('pdf.selection.local.document', 'wizard_id', 
                                       string='Documentos Locales')
    
    # Para documentos de Alfresco
    current_folder_id = fields.Many2one('alfresco.folder', string='Carpeta Actual')
    alfresco_file_ids = fields.Many2many('alfresco.file', string='Archivos de Alfresco Disponibles',
                                       compute='_compute_alfresco_files')
    selected_alfresco_ids = fields.Many2many('alfresco.file', 'pdf_selection_alfresco_rel',
                                           'wizard_id', 'file_id', string='Archivos Seleccionados')
    
    # Navegación de carpetas
    folder_path = fields.Char(string='Ruta Actual', compute='_compute_folder_path')
    parent_folder_id = fields.Many2one('alfresco.folder', string='Carpeta Padre', 
                                     compute='_compute_parent_folder')
    child_folder_ids = fields.Many2many('alfresco.folder', string='Subcarpetas',
                                      compute='_compute_child_folders')
    
    # Contadores
    local_count = fields.Integer(string='Documentos Locales', compute='_compute_counts')
    selected_count = fields.Integer(string='Documentos Seleccionados', compute='_compute_counts')

    @api.depends('local_document_ids', 'selected_alfresco_ids')
    def _compute_counts(self):
        for record in self:
            record.local_count = len(record.local_document_ids)
            record.selected_count = len(record.selected_alfresco_ids)

    @api.depends('current_folder_id')
    def _compute_folder_path(self):
        for record in self:
            if record.current_folder_id:
                record.folder_path = record.current_folder_id.complete_path or '/'
            else:
                record.folder_path = '/'

    @api.depends('current_folder_id')
    def _compute_parent_folder(self):
        for record in self:
            if record.current_folder_id and record.current_folder_id.parent_id:
                record.parent_folder_id = record.current_folder_id.parent_id
            else:
                record.parent_folder_id = False

    @api.depends('current_folder_id')
    def _compute_child_folders(self):
        for record in self:
            if record.current_folder_id:
                record.child_folder_ids = record.current_folder_id.child_ids
            else:
                # Mostrar carpetas raíz
                root_folders = self.env['alfresco.folder'].search([('parent_id', '=', False)])
                record.child_folder_ids = root_folders

    @api.depends('current_folder_id')
    def _compute_alfresco_files(self):
        for record in self:
            if record.current_folder_id:
                _logger.info("[v0] Loading PDF files for folder: %s (ID: %s)", 
                           record.current_folder_id.name, record.current_folder_id.id)
                
                # Buscar archivos PDF en la carpeta actual
                pdf_files = self.env['alfresco.file'].search([
                    ('folder_id', '=', record.current_folder_id.id),
                    ('name', 'ilike', '%.pdf')
                ])
                
                _logger.info("[v0] Found %d PDF files in folder %s", 
                           len(pdf_files), record.current_folder_id.name)
                
                for pdf_file in pdf_files:
                    _logger.info("[v0] PDF file: %s (ID: %s)", pdf_file.name, pdf_file.id)
                
                record.alfresco_file_ids = pdf_files
            else:
                _logger.info("[v0] No current folder selected, clearing PDF files")
                record.alfresco_file_ids = False

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto"""
        res = super(PdfSelectionWizard, self).default_get(fields_list)
        
        # Si no hay carpeta actual, usar la primera carpeta raíz disponible
        if 'current_folder_id' in fields_list and not res.get('current_folder_id'):
            root_folder = self.env['alfresco.folder'].search([('parent_id', '=', False)], limit=1)
            if root_folder:
                res['current_folder_id'] = root_folder.id
                self.current_folder_id = False
        
        return res

    def action_navigate_to_folder(self, folder_id):
        """Navega a una carpeta específica"""
        self.ensure_one()
        folder = self.env['alfresco.folder'].browse(folder_id)
        if folder.exists():
            self.current_folder_id = folder
        return self._reload_wizard()

    def action_navigate_to_folder_wizard(self):
        """Navigate to folder from wizard context"""
        self.ensure_one()
        folder_id = self.env.context.get('active_id')
        if folder_id:
            _logger.info("[v0] Navigating to folder ID: %s", folder_id)
            folder = self.env['alfresco.folder'].browse(folder_id)
            if folder.exists():
                self.current_folder_id = folder
                _logger.info("[v0] Successfully navigated to folder: %s", folder.name)
            else:
                _logger.warning("[v0] Folder ID %s does not exist", folder_id)
        return self._reload_wizard()

    def action_go_to_parent(self):
        """Navega a la carpeta padre"""
        self.ensure_one()
        if self.parent_folder_id:
            self.current_folder_id = self.parent_folder_id
        else:
            self.current_folder_id = False
        return self._reload_wizard()

    def action_go_to_root(self):
        """Navega a la carpeta raíz"""
        self.ensure_one()
        self.current_folder_id = False
        return self._reload_wizard()

    def action_add_local_document(self):
        """Agrega un nuevo documento local"""
        self.ensure_one()
        self.env['pdf.selection.local.document'].create({
            'wizard_id': self.id,
            'name': 'Nuevo Documento.pdf',
        })
        return self._reload_wizard()

    def action_remove_local_document(self, document_id):
        """Elimina un documento local"""
        document = self.env['pdf.selection.local.document'].browse(document_id)
        if document.wizard_id.id == self.id:
            document.unlink()
        return self._reload_wizard()

    def action_select_file(self):
        """Selecciona un archivo de Alfresco para firma"""
        self.ensure_one()
        file_id = self.env.context.get('active_id')
        
        if file_id:
            _logger.info("[FILE_SELECTION] Selecting file ID: %s", file_id)
            file_obj = self.env['alfresco.file'].browse(file_id)
            
            if file_obj.exists() and file_obj not in self.selected_alfresco_ids:
                self.selected_alfresco_ids = [(4, file_id)]
                _logger.info("[FILE_SELECTION] File '%s' added to selection", file_obj.name)
            else:
                _logger.warning("[FILE_SELECTION] File already selected or doesn't exist: %s", file_id)
        
        return self._reload_wizard()

    def action_remove_file(self):
        """Remueve un archivo de la selección"""
        self.ensure_one()
        file_id = self.env.context.get('active_id')
        
        if file_id:
            _logger.info("[FILE_SELECTION] Removing file ID: %s", file_id)
            file_obj = self.env['alfresco.file'].browse(file_id)
            
            if file_obj in self.selected_alfresco_ids:
                self.selected_alfresco_ids = [(3, file_id)]
                _logger.info("[FILE_SELECTION] File '%s' removed from selection", file_obj.name)
        
        return self._reload_wizard()

    def action_confirm_selection(self):
        """Confirma la selección y regresa al wizard principal"""
        self.ensure_one()
        
        if self.selection_type == 'local':
            if not self.local_document_ids:
                raise UserError(_('Debe agregar al menos un documento local.'))
            
            # Validar que todos los documentos tengan contenido
            for doc in self.local_document_ids:
                if not doc.pdf_content:
                    raise UserError(_('El documento "%s" no tiene contenido PDF.') % doc.name)
            
            # Crear documentos temporales para el workflow
            temp_docs = []
            for doc in self.local_document_ids:
                temp_doc = self.env['signature.workflow.document.temp'].create({
                    'name': doc.name,
                    'pdf_content': doc.pdf_content,
                    'pdf_filename': doc.pdf_filename,
                })
                temp_docs.append(temp_doc.id)
            
            # Actualizar el wizard principal
            self.workflow_wizard_id.selected_document_ids = [(6, 0, temp_docs)]
        
        else:  # alfresco
            if not self.selected_alfresco_ids:
                raise UserError(_('Debe seleccionar al menos un archivo de Alfresco.'))
            
            # Crear documentos temporales para el workflow
            temp_docs = []
            for file in self.selected_alfresco_ids:
                temp_doc = self.env['signature.workflow.document.temp'].create({
                    'name': file.name,
                    'alfresco_file_id': file.id,
                })
                temp_docs.append(temp_doc.id)
            
            # Actualizar el wizard principal
            self.workflow_wizard_id.selected_document_ids = [(6, 0, temp_docs)]
        
        # Cerrar este wizard y mostrar el principal
        return {
            'type': 'ir.actions.act_window',
            'name': 'Iniciar Flujo de Firma',
            'res_model': 'signature.workflow.wizard',
            'res_id': self.workflow_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _reload_wizard(self):
        """Recarga el wizard actual"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Seleccionar Documentos PDF',
            'res_model': 'pdf.selection.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class PdfSelectionLocalDocument(models.TransientModel):
    _name = 'pdf.selection.local.document'
    _description = 'Documento Local para Selección'

    wizard_id = fields.Many2one('pdf.selection.wizard', string='Wizard', required=True, ondelete='cascade')
    name = fields.Char(
        string='Nombre del Documento', 
        required=True, # Agrega este valor por defecto
    )
    pdf_content = fields.Binary(string='Archivo PDF', required=True)
    pdf_filename = fields.Char(string='Nombre del Archivo')
    
    # Información del archivo
    file_size = fields.Char(string='Tamaño', compute='_compute_file_info')
    is_valid_pdf = fields.Boolean(string='PDF Válido', compute='_compute_file_info')

    @api.depends('pdf_content')
    def _compute_file_info(self):
        for record in self:
            if record.pdf_content:
                try:
                    # Calcular tamaño
                    size_bytes = len(base64.b64decode(record.pdf_content))
                    if size_bytes < 1024:
                        record.file_size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        record.file_size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        record.file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                    
                    # Validar que sea PDF
                    pdf_data = base64.b64decode(record.pdf_content)
                    record.is_valid_pdf = pdf_data.startswith(b'%PDF')
                    
                except Exception as e:
                    record.file_size = "Error"
                    record.is_valid_pdf = False
                    _logger.error(f"Error procesando archivo PDF: {e}")
            else:
                record.file_size = "N/A"
                record.is_valid_pdf = False

    @api.onchange('pdf_content', 'pdf_filename')
    def _onchange_pdf_content(self):
        """Actualiza el nombre basado en el archivo subido"""
        # Asegurarse de que name es una cadena antes de usar endswith
        current_name = self.name or ''
        if self.pdf_filename and not current_name.endswith('.pdf'):
            self.name = self.pdf_filename

    def action_remove(self):
        """Elimina este documento"""
        self.unlink()
        return self.wizard_id._reload_wizard()
