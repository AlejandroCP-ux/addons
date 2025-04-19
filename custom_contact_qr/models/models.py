# models.py
import io
import base64
import qrcode
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    qr_code = fields.Binary(string='QR Code', compute="_compute_generate_qr_code", store=False, attachment=False)
    qr_code_low = fields.Binary(string='QR Code Low', compute="_compute_generate_qr_code", store=False, attachment=False)

    
    @api.depends('name','email','function','parent_id','mobile','website')
    def _compute_generate_qr_code(self):
        for partner in self:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=4)
            qr_low = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=4, border=2)
            org = partner.parent_id.name or ''
            voz = partner.phone or ''
            cell =partner.mobile or ''
            mail = partner.email or ''
            website = partner.website or ''
            qr_low.add_data(f'BEGIN:VCARD\nVERSION:3.0\nTEL;TYPE=CELL:{cell}\nEMAIL:{mail}\nEND:VCARD')
            qr_low.make(fit=True)
            qr.add_data(f'BEGIN:VCARD\nVERSION:3.0\nFN:{partner.name}\nORG:{org}\nTEL;TYPE=CELL,work:{cell}\nEMAIL:{mail}\nURL:{website}\nEND:VCARD')
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            temp = io.BytesIO()
            img.save(temp, format="PNG")
            partner.qr_code = base64.b64encode(temp.getvalue())
            img_low = qr_low.make_image(fill_color="black", back_color="white")
            temp_low = io.BytesIO()
            img_low.save(temp_low, format="PNG")
            partner.qr_code_low = base64.b64encode(temp_low.getvalue())