# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CustomReport(models.Model):
    _name = 'custom.report'
    _description = 'Configuración de Reportes Personalizados'

    name = fields.Char(string='Nombre del Reporte', required=True)
    model_id = fields.Many2one(
        'ir.model',
        string='Modelo Relacionado',
        required=True,
        ondelete='cascade'
    )
    report_action_id = fields.Many2one(
        'ir.actions.report',
        string='Acción de Reporte',
        required=True,
        domain="[('model', '=', model)]",
        ondelete='cascade'
    )
    model = fields.Char(related='model_id.model', readonly=True)
    active = fields.Boolean(string='Activo', default=True)