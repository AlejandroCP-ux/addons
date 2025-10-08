from odoo import models, fields

class DocumentoFirma(models.TransientModel):  
    _inherit = 'documento.firma'

    wizard_id = fields.Many2one('firma.documento.wizard', string='Wizard')
