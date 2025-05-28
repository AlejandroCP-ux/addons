import base64
import logging
import requests
from odoo import models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

class Report(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None, **kwargs):
        # Llamamos al super para obtener el contenido del PDF
        pdf_content, report_type = super(Report, self)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data, **kwargs
        )

        # Obtenemos el mapeo de Alfresco
        mapping = self.env['alfresco.report.mapping'].search([
            ('report_id.report_name', '=', report_ref),
        ], limit=1)

        # Obtenemos configuración de Alfresco
        RCS = self.env['ir.config_parameter'].sudo()
        url = RCS.get_param('asi_alfresco_integration.alfresco_server_url')
        user = RCS.get_param('asi_alfresco_integration.alfresco_username')
        pwd  = RCS.get_param('asi_alfresco_integration.alfresco_password')

        if not url or not mapping:
            _logger.warning("No hay configuración o mapeo para subir a Alfresco.")
            return pdf_content, report_type

        # Obtenemos la acción de reporte y evaluamos print_report_name dinámicamente
        report_action = self.env['ir.actions.report']._get_report_from_name(report_ref)
        if report_action.print_report_name:
            record = self.env[report_action.model].browse(res_ids[0])
            context = {'object': record, 'o': record, 'user': self.env.user, 'res_ids': res_ids}
            try:
                filename = safe_eval(report_action.print_report_name, context)
                filename = f"{filename}.pdf"
            except Exception as e:
                _logger.warning("Error evaluando print_report_name: %s", e)
                filename = f"{report_ref}_{'_'.join(map(str, res_ids or []))}.pdf"
        else:
            filename = f"{report_ref}_{'_'.join(map(str, res_ids or []))}.pdf"

        _logger.info("Nombre del archivo para Alfresco: %s", filename)

        try:
            # Verificar si el archivo ya existe en la carpeta de Alfresco
            search_url = f"{url}/alfresco/api/-default-/public/search/versions/1/search"
            query_payload = {
                "query": {
                    "query": f"PATH:'/app:company_home/cm:{mapping.folder_name}/*' AND cm:name:'{filename}'"
                }
            }
            headers = {'Content-Type': 'application/json'}
            resp_search = requests.post(search_url, json=query_payload, auth=(user, pwd), headers=headers)
            resp_search.raise_for_status()
            search_data = resp_search.json()

            if search_data['list']['pagination']['count'] > 0:
                # Documento existente, subir nueva versión
                existing_node_id = search_data['list']['entries'][0]['entry']['id']
                version_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{existing_node_id}/content"
                resp_version = requests.put(
                    version_url,
                    data=pdf_content,
                    auth=(user, pwd),
                    headers={'Content-Type': 'application/pdf'}
                )
                resp_version.raise_for_status()
                _logger.info("Nueva versión subida a Alfresco para %s", filename)
            else:
                # Documento nuevo, subirlo
                endpoint = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{mapping.folder_node_id}/children"
                files = {'filedata': (filename, pdf_content)}
                params = {'autoRename': 'true'}
                resp_upload = requests.post(
                    endpoint,
                    files=files,
                    params=params,
                    auth=(user, pwd),
                )
                resp_upload.raise_for_status()
                _logger.info("Archivo nuevo subido a Alfresco: %s", filename)

        except Exception as e:
            _logger.error("Error subiendo PDF a Alfresco: %s", e)

        return pdf_content, report_type