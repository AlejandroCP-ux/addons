import logging
import requests
from odoo import models

_logger = logging.getLogger(__name__)

class Report(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None, **kwargs):
        # Llamamos al super con los mismos nombres de parámetro
        pdf_content, report_type = super(Report, self)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data, **kwargs
        )

        # Obtenemos el mapeo
        mapping = self.env['alfresco.report.mapping'].search([
            ('report_id.report_name', '=', report_ref),
        ], limit=1)

        # Si no hay URL o mapeo, devolvemos el PDF tal cual
        RCS = self.env['ir.config_parameter'].sudo()
        url = RCS.get_param('asi_alfresco_integration.alfresco_server_url')
        user = RCS.get_param('asi_alfresco_integration.alfresco_username')
        pwd  = RCS.get_param('asi_alfresco_integration.alfresco_password')
        if not url or not mapping:
            _logger.warning("No hay configuración o mapeo para subir a Alfresco.")
            return pdf_content, report_type
        _logger.warning(" ************ user: %s ****  PAss %s",user,pwd )
        # Construimos el nombre de archivo
        filename = f"{report_ref}_{'_'.join(map(str, res_ids or []))}.pdf"
        for record in self:
          filename = f"{record.name}.pdf"
          _logger.info("**************** record  %s **************************** ",record)
        
        try:
            endpoint = (
                f"{url}/alfresco/api/-default-/public/"
                f"alfresco/versions/1/nodes/{mapping.folder_node_id}/children"
            )
            files = {'filedata': (filename, pdf_content)}
            params = {'autoRename': 'true'}
            resp = requests.post(
                endpoint,
                files=files,
                params=params,
                auth=(user, pwd),
            )
            resp.raise_for_status()
            _logger.info("***********%s **************************** PDF subido a Alfresco: %s",filename, resp.json())
        except Exception as e:
            _logger.error("********************  Error subiendo PDF a Alfresco: %s", e)

        return pdf_content, report_type
