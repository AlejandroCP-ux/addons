

import logging
import requests
from odoo import models

_logger = logging.getLogger(__name__)

class Report(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None, **kwargs):
        # Llamamos al super para obtener el contenido del PDF
        pdf_content, report_type = super(Report, self)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data, **kwargs
        )

        mapping = self.env['alfresco.report.mapping'].search([
            ('report_id.report_name', '=', report_ref),
        ], limit=1)

        RCS = self.env['ir.config_parameter'].sudo()
        url = RCS.get_param('asi_alfresco_integration.alfresco_server_url')
        user = RCS.get_param('asi_alfresco_integration.alfresco_username')
        pwd  = RCS.get_param('asi_alfresco_integration.alfresco_password')

        if not url or not mapping:
            _logger.warning("No hay configuración o mapeo para subir a Alfresco.")
            return pdf_content, report_type

        # Obtenemos el report_action y el print_report_name evaluado dinámicamente
        report_action = self.env['ir.actions.report']._get_report_from_name(report_ref)
        if report_action.print_report_name:
            # Evaluamos el nombre usando el primer registro (res_ids[0])
            record = self.env[report_action.model].browse(res_ids[0])
            qweb_context = {'object': record, 'res_ids': res_ids}
            filename = self.env['ir.qweb']._render(report_action.print_report_name, qweb_context)
            filename = f"{filename}.pdf"
        else:
            filename = f"{report_ref}_{'_'.join(map(str, res_ids or []))}.pdf"

        _logger.info("*********** Nombre del archivo para Alfresco: %s", filename)

        try:
            # Primero verificamos si el archivo ya existe en la carpeta (por nombre)
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
                existing_node_id = search_data['list']['entries'][0]['entry']['id']
                # Si existe, subimos una nueva versión
                endpoint = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{existing_node_id}/content"
                resp_version = requests.put(
                    endpoint,
                    data=pdf_content,
                    auth=(user, pwd),
                    headers={'Content-Type': 'application/pdf'}
                )
                resp_version.raise_for_status()
                _logger.info("*********** Nueva versión subida a Alfresco para %s", filename)
            else:
                # Si no existe, subimos un nuevo archivo
                endpoint = (
                    f"{url}/alfresco/api/-default-/public/"
                    f"alfresco/versions/1/nodes/{mapping.folder_node_id}/children"
                )
                files = {'filedata': (filename, pdf_content)}
                params = {'autoRename': 'true'}
                resp_upload = requests.post(
                    endpoint,
                    files=files,
                    params=params,
                    auth=(user, pwd),
                )
                resp_upload.raise_for_status()
                _logger.info("*********** Archivo nuevo subido a Alfresco: %s", filename)

        except Exception as e:
            _logger.error("******************** Error subiendo PDF a Alfresco: %s", e)

        return pdf_content, report_type
