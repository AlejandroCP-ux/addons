from odoo import models, fields

class AlfrescoFile(models.Model):
    _name = 'alfresco.file'
    _description = 'Archivo importado desde Alfresco'

    name = fields.Char(string="Nombre del archivo", required=True)
    folder_id = fields.Many2one('alfresco.folder', string="Carpeta", ondelete='cascade')
    alfresco_node_id = fields.Char(string="ID de nodo en Alfresco", readonly=True, required=True, index=True)
    mime_type = fields.Char(string="MIME Type")
    file_size = fields.Integer(string="Tamaño (bytes)")
    modified_at = fields.Datetime(string="Modificado en Alfresco")
