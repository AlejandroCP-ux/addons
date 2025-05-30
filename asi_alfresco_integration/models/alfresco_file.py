from odoo import models, fields

class AlfrescoFile(models.Model):
    _name = 'alfresco.file'
    _description = 'Archivo en Alfresco'

    name = fields.Char(string='Nombre del archivo')
    node_id = fields.Char(string='Node ID')
    mimetype = fields.Char(string='Tipo MIME')
    folder_id = fields.Many2one('alfresco.folder', string='Carpeta')
    url = fields.Char(string='URL pública')