from odoo import models

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _postprocess_contents(self, values):
        values = super()._postprocess_contents(values)
        if values.get('name', '').startswith('web.assets_'):
            if values.get('raw'):
                values['raw'] = values['raw'].decode().replace('https://fonts.googleapis.com/css', '/css/font/google').encode()
        return values
