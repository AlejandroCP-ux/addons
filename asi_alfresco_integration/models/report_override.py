import logging
import requests
import re
import json
from odoo import models
from datetime import datetime
from io import BytesIO


_logger = logging.getLogger(__name__)


class Report(models.Model):
    _inherit = 'ir.actions.report'


    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None, **kwargs):
        pdf_content, report_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data, **kwargs
        )

        mapping = self.env['alfresco.report.mapping'].search([
            ('report_id.report_name', '=', report_ref),
        ], limit=1)

        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')

        if not url or not mapping:
            _logger.warning("Falta configuración o mapeo para Alfresco.")
            return pdf_content, report_type

        filename, properties = self._build_metadata(report_ref, res_ids)
        if not filename:
            filename = f"{report_ref}_{'_'.join(map(str, res_ids or []))}.pdf"

        try:
            node_id = self._find_existing_file(url, user, pwd, filename, mapping.folder_node_id)
            if node_id:
                # Comparar contenido. Temporalmente obvio esta opcion y siempre sube una version porque no tenemos la herramienta para comparar pdfs
                existing_content = self._download_existing_content(url, user, pwd, node_id)
                if  True:
                    self._update_existing_file(url, user, pwd, node_id, pdf_content, filename)
                else:
                    _logger.info("El contenido es idéntico. No se sube nueva versión.")
            else:
                self._upload_new_file(url, user, pwd, mapping.folder_node_id, filename, pdf_content, properties)

        except Exception as e:
            _logger.error("Error durante subida a Alfresco: %s", e)

        return pdf_content, report_type

    def _build_metadata(self, report_ref, res_ids):
        filename = None
        properties = {}
        report = self._get_report(report_ref)
        if report.model == 'account.move' and res_ids:
            invoice = self.env['account.move'].browse(res_ids[0])
            if invoice.exists():
                filename = re.sub(r'[\\/*?:"<>|]', '_', invoice.name) + ".pdf"
                if invoice.partner_id:
                    properties = {
                        "cliente_id": str(invoice.partner_id.id),
                        "cliente_nombre": invoice.partner_id.name or "",
                        "cliente_nif": invoice.partner_id.vat or "",
                        "factura_numero": invoice.name,
                        "factura_fecha": invoice.invoice_date.isoformat() if invoice.invoice_date else "",
                        "factura_total": float(invoice.amount_total),
                        "fecha_subida": datetime.now().isoformat()
                    }
        return filename, properties

    def _find_existing_file(self, url, user, pwd, filename, folder_node_id):
        search_url = f"{url}/alfresco/api/-default-/public/search/versions/1/search"
        query = {
            "query": {
                "language": "afts",
                "query": f'cm:name:"{filename}" AND ANCESTOR:"workspace://SpacesStore/{folder_node_id}"'
            },
            "include": ["properties"],
            "paging": {"maxItems": 1, "skipCount": 0}
        }
        response = requests.post(
            search_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(query),
            auth=(user, pwd),
        )
        response.raise_for_status()
        results = response.json().get('list', {}).get('entries', [])
        return results[0]['entry']['id'] if results else None

    def _download_existing_content(self, url, user, pwd, node_id):
        download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
        response = requests.get(download_url, auth=(user, pwd))
        response.raise_for_status()
        return response.content

    def _upload_new_file(self, url, user, pwd, folder_node_id, filename, pdf_content, properties):
        endpoint = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{folder_node_id}/children"
        files = {'filedata': (filename, pdf_content)}
        data = {"json": json.dumps({
            "name": filename,
            "nodeType": "cm:content",
            "properties": properties
        })}
        response = requests.post(endpoint, files=files, data=data, params={'autoRename': 'true'}, auth=(user, pwd))
        response.raise_for_status()
        _logger.info("Archivo nuevo subido a Alfresco: %s", filename)

    def _update_existing_file(self, url, user, pwd, node_id, pdf_content, filename):
        update_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
        response = requests.put(
            update_url,
            headers={"Content-Type": "application/pdf"},
            data=pdf_content,
            auth=(user, pwd),
        )
        response.raise_for_status()
        _logger.info("Versión actualizada correctamente para el archivo %s", filename)
