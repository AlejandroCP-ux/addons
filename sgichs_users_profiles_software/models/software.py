# -*- coding: utf-8 -*-
from odoo import models, fields

class ITSoftware(models.Model):
    _inherit = 'it.asset.software'

    # Relación inversa para saber en qué perfiles está permitido este software.
    # El nombre 'softwares_ids' es el del campo en 'it.user.profile'.
    profile_ids = fields.Many2many(
        'it.user.profile',
        'it_user_profile_software_rel',  # Nombre de la tabla de relación explícita
        'software_id', 
        'profile_id', 
        string='Perfiles Permitidos',
        help="Muestra en qué perfiles de usuario está permitido este software."
    )