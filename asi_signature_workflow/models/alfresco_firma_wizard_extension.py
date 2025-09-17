# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AlfrescoFirmaWizardExtension(models.TransientModel):
    _inherit = 'alfresco.firma.wizard'
    
    from_workflow = fields.Boolean(string='Desde Flujo de Trabajo', default=False)
    workflow_id = fields.Many2one('signature.workflow', string='Flujo de Trabajo')
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
                    'signature_role': workflow.signature_role_id.id,
                    'signature_position': workflow.signature_position,
                })
                _logger.info(f"Wizard de Alfresco configurado desde flujo {workflow.id} con rol {workflow.signature_role_id.name} y posición {workflow.signature_position}")
        
        
        return res

    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        result = super(AlfrescoFirmaWizardExtension, self).action_firmar_documentos()
        
        if self.from_workflow and self.workflow_id and self.status == 'completado':
            try:
                self.workflow_id.action_mark_as_signed()
                _logger.info(f"Flujo {self.workflow_id.id} marcado como firmado automáticamente")
            except Exception as e:
                _logger.error(f"Error marcando flujo como firmado: {e}")
        
        return result

    @api.onchange('signature_role', 'signature_position')
    def _onchange_signature_config(self):
        """Prevenir cambios en configuración cuando viene de flujo de trabajo"""
        if self.readonly_signature_config and self.from_workflow:
            if self.workflow_id:
                self.signature_role = self.workflow_id.signature_role_id.id
                self.signature_position = self.workflow_id.signature_position
                return {
                    'warning': {
                        'title': _('Configuración Bloqueada'),
                        'message': _('El rol y posición de firma están definidos por el creador del flujo de trabajo y no pueden ser modificados.')
                    }
                }
