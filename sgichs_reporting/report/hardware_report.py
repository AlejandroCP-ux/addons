# -*- coding: utf-8 -*-
from odoo import models

class HardwareReport(models.AbstractModel):
    _name = 'report.sgichs_reporting.hardware_technical_sheet'
    _description = 'Reporte de Ficha Técnica de Hardware'
    
    def _get_report_values(self, docids, data=None):
        docs = self.env['it.asset.hardware'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'it.asset.hardware',
            'docs': docs,
            'get_components': self._get_components,
        }
    
    def _get_components(self, hardware):
        return hardware.components_ids.sorted(key=lambda r: r.type)