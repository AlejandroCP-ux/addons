# models/report_integration.py
import requests
from odoo import models, api, fields
from requests.auth import HTTPBasicAuth
from datetime import datetime

class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    @api.model
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None, **kwargs):
        # 1) Llamo al super para obtener el PDF binario
        pdf_content, report_type = super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data, **kwargs)

        # 2) Identifico de qué modelo y registro viene
        #    report_ref puede ser: 'module.report_template_name'
        #    res_ids es una lista de ids. Si solo genera uno, tomo el primero.
        if res_ids:
            res_model = self.env['ir.actions.report'].browse(
                self.env.ref(report_ref).id
            ).report_file  # a veces es mejor: self.env.ref(report_ref).model
            # Sin embargo, para mayor robustez, usamos 'report_ref' para encontrar el modelo:
            record_model = self.env[self.env.ref(report_ref).model]  
            record_id = res_ids[0]  # suponiendo que genera un solo documento a la vez
        else:
            # Si no hay res_ids (ej: reportes globales), puedes saltarte la integración
            return pdf_content, report_type

        # 3) Preparo las credenciales y URL base de Alfresco desde parámetros
        config = self.env['ir.config_parameter'].sudo()
        base_url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user     = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd      = config.get_param('asi_alfresco_integration.alfresco_password')
        repo_id  = config.get_param('asi_alfresco_integration.alfresco_repo_id')
        if not base_url or not user or not pwd or not repo_id:
            return pdf_content, report_type

        # 4) Construyo la ruta a la carpeta destino en Alfresco
        #    Aquí puedes basarte en el modelo origen para elegir carpeta. Por ejemplo:
        #    folder = self.env['alfresco.folder'].search([('name', '=', record_model._name)], limit=1)
        #    o puedes almacenar un campo 'folder_id' en ir.actions.report como ya tienes.
        #    Supongamos que en ir.actions.report existe campo Many2one('alfresco.folder', 'folder_id')
        report_action = self.env.ref(report_ref)
        alf_folder = report_action.folder_id  # modelado previamente en tu vista
        if not alf_folder:
            return pdf_content, report_type

        node_parent = alf_folder.node_id  # este es el ID de la carpeta en Alfresco
        if not node_parent:
            return pdf_content, report_type

        # 5) Subo el PDF a Alfresco con el endpoint CMIS o REST v1
        #    Ejemplo usando REST v1 “create version”:
        upload_url = (
            f"{base_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/"
            f"{node_parent}/children"
        )
        headers = {'Accept': 'application/json'}
        files = {
            'filedata': (
                f"{record_model._name}_{record_id}.pdf",
                pdf_content,
                'application/pdf'
            )
        }
        auth = HTTPBasicAuth(user, pwd)

        try:
            response = requests.post(upload_url, auth=auth, headers=headers, files=files, timeout=15)
            response.raise_for_status()
        except Exception as e:
            _logger.error(f"Error subiendo reporte a Alfresco: {e}")
            return pdf_content, report_type

        entry = response.json().get('entry', {})
        new_node_id = entry.get('id')
        version_series = entry.get('versionSeriesId')

        if new_node_id and version_series:
            # 6) Construyo la URL de descarga de la última versión
            download_url = (
                f"{base_url}/alfresco/api/-default-/public/alfresco/versions/1/"
                f"nodes/{new_node_id}/content"
            )
            # 7) Busco o creo el mapping
            mapping = self.env['alfresco.report.mapping'].sudo().search([
                ('res_model', '=', record_model._name),
                ('res_id',    '=', record_id),
            ], limit=1)
            vals = {
                'version_series_id': version_series,
                'node_id':           new_node_id,
                'url':               download_url,
                'last_update':       fields.Datetime.now(),
            }
            if not mapping:
                vals.update({
                    'res_model': record_model._name,
                    'res_id':    record_id,
                })
                self.env['alfresco.report.mapping'].sudo().create(vals)
            else:
                mapping.sudo().write(vals)

        return pdf_content, report_type

        
    
    def _evaluate_report_filename(self, report, record):
        """
        Evalua el campo `print_report_name` del reporte ir.actions.report
        usando safe_eval en el contexto {'object': record}. Devuelve
        el string limpio (sin caracteres invalidos) + '.pdf'.
        Si falla o no hay print_report_name, retorna None.
        """
        if not report or not report.print_report_name or not record:
            return None

        try:
            # safe_eval sobre la expresion (por ejemplo, 'object.partner_id.name + "_" + object.name')
            result = safe_eval(report.print_report_name, {'object': record})
            # Reemplazar caracteres no validos para nombre de fichero
            clean_result = re.sub(r'[\\/*?:"<>|]', '_', result)
            return clean_result + '.pdf'
        except Exception as e:
            _logger.warning(
                "Error al evaluar print_report_name para reporte '%s': %s",
                report.name, e
            )
            return None

    def _build_metadata(self, report_ref, res_ids):
        """
        Construye metadatos (properties) para Alfresco segun el tipo de reporte.
        Actualmente, si el modelo es 'account.move', agrega datos de factura.
        """
        filename = None
        properties = {}
        report = self._get_report(report_ref)

        if not report or not res_ids:
            return None, {}

        Model = self.env[report.model]
        record = Model.browse(res_ids[0])
        if not record.exists():
            return None, {}

        # Generar metadatos especificos si es factura
        if report.model == 'account.move':
            properties = {
                "cliente_id": str(record.partner_id.id),
                "cliente_nombre": record.partner_id.name or "",
                "cliente_nif": record.partner_id.vat or "",
                "factura_numero": record.name,
                "factura_fecha": record.invoice_date.isoformat() if record.invoice_date else "",
                "factura_total": float(record.amount_total),
                "fecha_subida": datetime.now().isoformat()
            }

        # Devolvemos None como filename aqui, porque normalmente _evaluate_report_filename
        # ya construye el nombre. Pero devolvemos properties utiles.
        return filename, properties

    def _find_existing_file(self, url, user, pwd, filename, folder_node_id):
        """
        Busca en Alfresco usando CMIS‐AFTS si ya existe un archivo con ese nombre
        dentro de la carpeta cuyo node_id es `folder_node_id`.
        Si lo encuentra, devuelve el node_id; si no, devuelve None.
        """
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
        """
        Descarga el contenido binario (PDF) de un nodo existente en Alfresco.
        """
        download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
        response = requests.get(download_url, auth=(user, pwd))
        response.raise_for_status()
        return response.content

    def _upload_new_file(self, url, user, pwd, folder_node_id, filename, pdf_content, properties):
        """
        Sube un nuevo archivo a Alfresco dentro de la carpeta indicada (folder_node_id).
        properties es un dict con metadatos JSON aceptados por Alfresco.
        """
        endpoint = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{folder_node_id}/children"
        files = {'filedata': (filename, pdf_content)}
        data = {
            "json": json.dumps({
                "name": filename,
                "nodeType": "cm:content",
                "properties": properties
            })
        }
        response = requests.post(
            endpoint,
            files=files,
            data=data,
            params={'autoRename': 'true'},
            auth=(user, pwd)
        )
        response.raise_for_status()

    def _update_existing_file(self, url, user, pwd, node_id, pdf_content, filename):
        """
        Reemplaza la version de un archivo existente en Alfresco.
        """
        update_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
        response = requests.put(
            update_url,
            headers={"Content-Type": "application/pdf"},
            data=pdf_content,
            auth=(user, pwd),
        )
        response.raise_for_status()

    def _extract_text_from_pdf(self, pdf_content):
        """
        Extrae texto de un PDF usando pypdf para comparar contenido.
        """
        try:
            reader = PdfReader(BytesIO(pdf_content))
            text = ''
            for page in reader.pages:
                text += page.extract_text() or ''
            return text.strip()
        except Exception as e:
            _logger.error("Error extrayendo texto del PDF: %s", e)
            return ''
