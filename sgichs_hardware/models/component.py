# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class Component(models.Model):
    _name = 'it.component'
    _description = 'Componente de TI'
    _order = 'model'

    model = fields.Char(string='Modelo', required=True)
    type = fields.Selection(
        related='subtype_id.type',
        string='Tipo',
        readonly=True,
        store=True
    )
    subtype_id = fields.Many2one(
        'it.component.subtype',
        string='Subtipo',
        required=True
    )
    serial_number = fields.Char(string='Número de Serie')
    inventory_number = fields.Char(string='Número de Inventario')
    status = fields.Selection(
        selection=[
            ('operational', 'Operativo'),
            ('maintenance', 'En Mantenimiento'),
            ('failed', 'Averiado'),
            ('retired', 'Retirado')
        ],
        string='Estado',
        default='operational'
    )
    hardware_id = fields.Many2one(
        'it.asset.hardware',
        string='Asignado a Hardware',
        ondelete='set null'
    )

    is_internal = fields.Boolean(
        string='Es Interno',
        compute='_compute_is_internal',
        store=False
    )

    _sql_constraints = [
        ('serial_number_uniq', 'unique(serial_number)', 'El número de serie debe ser único!'),
    ]
    
    @api.depends('subtype_id.is_internal')
    def _compute_is_internal(self):
        for record in self:
            record.is_internal = record.subtype_id.is_internal if record.subtype_id else False

    @api.constrains('hardware_id')
    def _check_hardware_assignment(self):
        for component in self.filtered(lambda c: c.hardware_id and c.serial_number):
            other_components = self.search([
                ('serial_number', '=', component.serial_number),
                ('id', '!=', component.id),
                ('hardware_id', '!=', False)
            ])
            if other_components:
                raise ValidationError(f"El componente con S/N {component.serial_number} ya está asignado a otro hardware.")

    def action_unassign_from_hardware(self):
        """Desasigna el componente del hardware actual"""
        if not self.hardware_id:
            raise UserError("Este componente no está asignado a ningún hardware.")
        
        # Registro de actividad para auditoría
        self.message_post(
            body=f"Componente desasignado del hardware: {self.hardware_id.name}"
        )
        
        self.hardware_id = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Desasignación exitosa',
                'message': 'El componente ha sido desasignado correctamente',
                'type': 'success',
                'sticky': False,
            }
        }