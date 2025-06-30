# -*- coding: utf-8 -*-

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Añadir los campos faltantes relacionados con Unsplash
    unsplash_access_key = fields.Char(string='Clave de acceso de Unsplash')
    unsplash_app_id = fields.Char(string='ID de aplicación de Unsplash')
    
    # Añadir otros campos que podrían estar relacionados con Unsplash
    unsplash_secret_key = fields.Char(string='Clave secreta de Unsplash')
    unsplash_url = fields.Char(string='URL de Unsplash')
