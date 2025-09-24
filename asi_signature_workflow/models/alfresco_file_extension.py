# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class AlfrescoFileExtension(models.Model):
    _inherit = 'alfresco.file'
    
    def action_select_file(self):
        """Selecciona este archivo en el wizard de selección PDF activo"""
        self.ensure_one()
        
        # Buscar el wizard activo de selección PDF
        wizard = self.env['pdf.selection.wizard'].search([
            ('selection_type', '=', 'alfresco')
        ], limit=1, order='id desc')
        
        if not wizard:
            _logger.warning("No se encontró wizard activo de selección PDF")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No hay un wizard de selección activo',
                    'type': 'warning',
                }
            }
        
        # Verificar que el archivo no esté ya seleccionado
        if self in wizard.selected_alfresco_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'El archivo "{self.name}" ya está seleccionado',
                    'type': 'info',
                }
            }
        
        # Agregar el archivo a la selección
        wizard.selected_alfresco_ids = [(4, self.id)]
        
        _logger.info("Archivo '%s' agregado a la selección del wizard", self.name)
        
        # Recargar el wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Seleccionar Documentos PDF',
            'res_model': 'pdf.selection.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_remove_file(self):
        """Remueve este archivo de la selección del wizard PDF activo"""
        self.ensure_one()
        
        # Buscar el wizard activo de selección PDF
        wizard = self.env['pdf.selection.wizard'].search([
            ('selection_type', '=', 'alfresco')
        ], limit=1, order='id desc')
        
        if not wizard:
            _logger.warning("No se encontró wizard activo de selección PDF")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No hay un wizard de selección activo',
                    'type': 'warning',
                }
            }
        
        # Verificar que el archivo esté seleccionado
        if self not in wizard.selected_alfresco_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'El archivo "{self.name}" no está en la selección',
                    'type': 'info',
                }
            }
        
        # Remover el archivo de la selección
        wizard.selected_alfresco_ids = [(3, self.id)]
        
        _logger.info("Archivo '%s' removido de la selección del wizard", self.name)
        
        # Recargar el wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Seleccionar Documentos PDF',
            'res_model': 'pdf.selection.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
