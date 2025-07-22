# sgichs_reporting/models/custom_reports.py
from odoo import models, fields, api

class CustomReport(models.Model):
    _name = 'custom.report'
    _description = 'Configuración de Reportes Personalizados'
    
    name = fields.Char(string='Nombre del Reporte', required=True)
    model_id = fields.Many2one(
        'ir.model', 
        string='Modelo Relacionado',
        required=True,
        domain="[('model', 'in', ['it.asset.hardware', 'it.incident', 'it.asset.software'])]",
        ondelete='cascade'  # CORRECCIÓN AQUÍ
    )
    template_id = fields.Many2one(
        'ir.ui.view', 
        string='Plantilla',
        domain="[('type', '=', 'qweb')]",
        required=True,
        ondelete='cascade'  # Añadir esto también
    )
    active = fields.Boolean(string='Activo', default=True)
    
    def generate_report(self, records):
        self.ensure_one()
        return self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            self.template_id.id,
            records.ids
        )