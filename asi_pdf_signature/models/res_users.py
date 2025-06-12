from odoo import models, fields, api, _
import base64
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    certificado_firma = fields.Binary(string='Certificado de Firma Digital (.p12)', attachment=True, help='Archivo .p12 para firma digital')
    nombre_certificado = fields.Char(string='Nombre del Certificado', help='Nombre del archivo del certificado')
    imagen_firma = fields.Binary(string='Imagen de Firma', attachment=True, help='Imagen que se utilizará para firmar documentos')
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = ['|', '|', ('login', operator, name), ('name', operator, name), ('email', operator, name)] + args
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)
    
    def tiene_requisitos_firma(self):
        """Verifica si el usuario tiene los requisitos para firmar documentos"""
        self.ensure_one()
        return bool(self.certificado_firma and self.imagen_firma)
