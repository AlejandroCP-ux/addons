# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ITUserProfile(models.Model):
    _name = 'it.user.profile'
    _description = 'Perfil de Usuario de TI'
    
    name = fields.Char(
        string='Nombre del Perfil', 
        required=True,
        help='Ej: Desarrollador, Trabajador, Administrador'
    )
    description = fields.Text(
        string='Descripción',
        help='Detalles sobre las características y permisos del perfil'
    )
    # Definir explícitamente la tabla de relación inversa
    user_ids = fields.Many2many(
        'it.user2', 
        'it_user_profile_rel2', # Solo la tabla de relación
        'profile_id2', # Columna de este modelo
        'user_id2', # Columna del otro modelo
        string='Usuarios Asociados',
        help='Usuarios que tienen este perfil asignado'
    )
    
    _sql_constraints = [
        ('unique_profile_name', 'UNIQUE(name)', 'El nombre del perfil debe ser único')
    ]