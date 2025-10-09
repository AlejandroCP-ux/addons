# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AlfrescoFirmaWizardExtension(models.TransientModel):
    _inherit = 'alfresco.firma.wizard'
    
    from_workflow = fields.Boolean(string='Desde Solicitud de Firma', default=False)
    workflow_id = fields.Many2one('signature.workflow', string='Solicitud de Firma')
    readonly_signature_config = fields.Boolean(string='Configuración de Solo Lectura', default=False)

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente"""
        res = super(AlfrescoFirmaWizardExtension, self).default_get(fields_list)
        
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
                
                if 'signature_opaque_background' in fields_list:
                    res['signature_opaque_background'] = workflow.signature_opaque_background
                
                if 'sign_all_pages' in fields_list:
                    res['sign_all_pages'] = workflow.sign_all_pages
                
                _logger.info(f"Wizard de Alfresco configurado desde solicitud de firma {workflow.id} con rol {workflow.signature_role_id.name if workflow.signature_role_id else 'N/A'} y posición {workflow.signature_position}")
        
        return res

    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        try:
            result = super(AlfrescoFirmaWizardExtension, self).action_firmar_documentos()
            
            # Solo procesar el flujo si la firma fue exitosa
            if self.from_workflow and self.workflow_id and self.status == 'completado':
                try:
                    self.workflow_id.action_mark_as_signed()
                    _logger.info(f"Solicitud {self.workflow_id.id} marcada como firmada automáticamente")
                except Exception as e:
                    _logger.error(f"Error marcando solicitud como firmada: {e}")
                    # No re-lanzar el error para no afectar la firma exitosa
            
            return result
            
        except Exception as e:
            _logger.error(f"Error en action_firmar_documentos desde solicitud {self.workflow_id.id if self.workflow_id else 'N/A'}: {e}")
            # Re-lanzar el error original para que el usuario lo vea
            raise

    @api.onchange('signature_role', 'signature_position', 'signature_opaque_background', 'sign_all_pages')
    def _onchange_signature_config(self):
        """Prevenir cambios en configuración cuando viene de solictud de firma"""
        if self.readonly_signature_config and self.from_workflow:
            if self.workflow_id:
                if self.workflow_id.signature_role_id:
                    self.signature_role = self.workflow_id.signature_role_id.id
                if self.workflow_id.signature_position:
                    self.signature_position = self.workflow_id.signature_position
                self.signature_opaque_background = self.workflow_id.signature_opaque_background
                self.sign_all_pages = self.workflow_id.sign_all_pages
                return {
                    'warning': {
                        'title': _('Configuración Bloqueada'),
                        'message': _('La configuración de firma está definida por el creador del solicitud de firma y no puede ser modificada.')
                    }
                }
