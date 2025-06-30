# -*- coding: utf-8 -*-

from odoo import models, fields, api

class FleetActivityType(models.Model):
    _name = 'fleet.activity.type'
    _description = 'Tipos de Actividad para Vehículos'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    description = fields.Text(string='Descripción')
    active = fields.Boolean(string='Activo', default=True)
    is_for_technological = fields.Boolean(
        string='¿Es para Vehículos Tecnológicos?', 
        default=False,
        help='Marque esta casilla si este tipo de actividad es específico para vehículos tecnológicos'
    )
    
    _sql_constraints = [
        ('name_technological_uniq', 'unique(name, is_for_technological)', 
         '¡Ya existe un tipo de actividad con este nombre para este tipo de vehículo!')
    ]
    
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.is_for_technological:
                name += ' (Tecnológico)'
            else:
                name += ' (Normal)'
            result.append((record.id, name))
        return result
