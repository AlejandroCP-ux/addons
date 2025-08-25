# -*- coding: utf-8 -*-
from odoo import models, api

class Hardware(models.Model):
    _inherit = 'it.asset.hardware'

    def action_generate_technical_sheet(self):
        """
        Esta función se encarga de llamar a la acción de reporte
        definida en este mismo módulo.
        """
        self.ensure_one()
        # Llama a la acción de reporte por su XML ID completo.
        return self.env.ref('sgichs_reporting.action_report_hardware_technical_sheet').report_action(self)