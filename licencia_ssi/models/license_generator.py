from odoo import models, fields, api
from Crypto.Cipher import AES
import base64
from datetime import datetime

class LicenseGenerator(models.Model):
    _name = 'license.generator'
    _description = 'Generador de Licencia'

    seed = fields.Char(string='Semilla', required=True)
    license_code = fields.Char(string='Licencia', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True)
    generated_date = fields.Datetime(string='Fecha de Generación', readonly=True)
    def generate_license(self):
        for record in self:
            try:
                
                # Clave secreta (debe ser de 16, 24 o 32 bytes)
                secret_key = "Desoft CTSI Sur, Amancio"  # Asegúrate de que tenga 16 caracteres

                # Crear un cifrador AES en modo ECB
                cipher = AES.new(secret_key.encode(), AES.MODE_ECB)

                # Rellenar la semilla con '{' para que sea múltiplo de 16 bytes
                padding = '{'
                seed_padded = record.seed + (16 - len(record.seed) % 16) * padding

                # Encriptar la semilla
                encrypted_license = cipher.encrypt(seed_padded.encode())

                # Codificar en base64
                license_code = base64.b64encode(encrypted_license).decode()

                # Guardar el resultado en el campo
                record.license_code = license_code
                 # Registrar la fecha de generación
                record.generated_date = datetime.now()
            except Exception as e:
                record.license_code = f"Error: {str(e)}"

    