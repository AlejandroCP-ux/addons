import logging
import requests
from odoo import models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

class Report(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, docids, data=None):
        pdf_content, report_type = super()._render_qweb_pdf(report_ref, docids, data)

        config = self.env['alfresco.config'].search([], limit=1)
        mapping = self.env['alfresco.report.mapping'].search([('report_id.report_name', '=', report_ref)], limit=1)

        if not config or not mapping:
            _logger.warning("Configuración o mapeo de reporte no encontrados para Alfresco.")
            return pdf_content, report_type

        try:
            url = f"{config.server_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{mapping.folder_node_id}/children"
            filename = f"{report_ref}_{'_'.join(map(str, docids))}.pdf"
            files = {'filedata': (filename, pdf_content)}
            params = {'autoRename': 'true'}

            response = requests.post(
                url,
                files=files,
                params=params,
                auth=(config.username, config.password)
            )
            response.raise_for_status()
            _logger.info(f"PDF subido correctamente a Alfresco: {response.json()}")
        except Exception as e:
            _logger.error(f"Error subiendo PDF a Alfresco: {e}")

        return pdf_content, report_type
