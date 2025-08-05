# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class AlfrescoFirmaWizard(models.TransientModel):
    _name = 'alfresco.firma.wizard'
    _description = 'Firmar documento en Alfresco'

    file_ids = fields.Many2many('alfresco.file', string='Archivos a firmar')
    signature_reason = fields.Char(string='Motivo de la firma', default="Aprobado por")
    signature_location = fields.Char(string='Ubicacion', default="ASI")
    signature_visible = fields.Boolean(string="Firma visible", default=True)

    def action_sign_pdf(self):
        self.ensure_one()
        if not self.file_ids:
            raise UserError("Debe seleccionar al menos un archivo para firmar.")
    
        for file in self.file_ids:
            if not file.pdf_file:
                raise UserError(f"El archivo '{file.name}' no tiene un PDF adjunto para firmar.")
    
            signed_pdf = self.env['res.users'].browse(self.env.uid).sign_pdf(
                file.pdf_file,
                reason=self.signature_reason,
                location=self.signature_location,
                visible=self.signature_visible
            )
    
            file.pdf_file = signed_pdf
            file.signed = True
    
        return {'type': 'ir.actions.act_window_close'}
