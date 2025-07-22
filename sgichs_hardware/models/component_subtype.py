# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ComponentSubtype(models.Model):
    _name = 'it.component.subtype'
    _description = 'Subtipo de Componente de TI'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    type = fields.Selection(
        selection=[
            ('internal', 'Interno'),
            ('peripheral', 'Periférico')
        ],
        string='Tipo de Componente',
        required=True
    )
    description = fields.Text(string='Descripción')
    component_count = fields.Integer(
        string='Cantidad de Componentes',
        compute='_compute_component_count'
    )

    _sql_constraints = [
        ('name_type_unique', 'UNIQUE(name, type)',
         'Ya existe un subtipo con este nombre para el mismo tipo de componente.'),
    ]

    def _compute_component_count(self):
        """Calcula el número de componentes que usan este subtipo."""
        for record in self:
            record.component_count = self.env['it.component'].search_count([
                ('subtype_id', '=', record.id)
            ])

    def action_view_components(self):
        """Acción para ver los componentes de este subtipo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Componentes: {self.name}',
            'res_model': 'it.component',
            'view_mode': 'tree,form',
            'domain': [('subtype_id', '=', self.id)],
            'context': {'default_subtype_id': self.id, 'default_type': self.type}
        }