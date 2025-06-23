import logging
import requests
import re
import json
from odoo import models, fields, api,_
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class Report(models.Model):
    _inherit = 'ir.actions.report'
    
    folder_id = fields.Many2one(
            'alfresco.folder',
            string='Carpeta Alfresco',
            help="Carpeta destino en Alfresco para este reporte"
        )
    metadata_field_ids = fields.Many2many(
        'ir.model.fields',
        'report_metadata_rel',
        'report_id',
        'field_id',
        string='Campos de Metadata',
        domain="[('model', '=', model)]"
    )  

    record_domain = fields.Char(
        string="Dominio para filtrar registros",
        help="Dominio para limitar los registros a imprimir automáticamente (formato: [('state','=','posted')])"
    )
        

    related_model_name = fields.Char(
        string="Modelo Relacionado",
        compute='_compute_related_model_name',
        store=False,
        # Añadimos este parámetro para forzar la notificación
        compute_sudo=True
    )
    
    def _compute_related_model_name(self):
        for rec in self:
            # Solo actualizamos si el valor ha cambiado
            if rec.related_model_name != rec.model:
                rec.related_model_name = rec.model
                
                # Forzar la actualización de la interfaz
                # Esta es la alternativa a _notify_computed_field_changed
                rec.modified(['related_model_name'])


    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None, **kwargs):
        """
        Para cada ID en res_ids:
         1) Genera un PDF individual (llamando a super con [id])
         2) Evalua el nombre del archivo usando print_report_name
         3) Sube o actualiza en Alfresco el PDF individual
        """
        # 1) Obtiene el PDF combinado tal y como Odoo lo haria por defecto
        pdf_content_combined, report_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data, **kwargs
        )
    
        _logger.debug("RES_IDS recibidos: %s  | REPORT_REF: %s", res_ids, report_ref)
    
        # 2) Obtiene el reporte y su carpeta configurada
        report = self._get_report(report_ref)
        folder = report.folder_id
    
        # 3) Carga configuracion de Alfresco desde parametros
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
    
        # Validaciones minimas
        if not url:
            _logger.warning("URL de servidor Alfresco no configurada. No se procesan subidas.")
            return pdf_content_combined, report_type
    
        if not folder:
            _logger.warning("El reporte '%s' no tiene carpeta Alfresco asignada.", report_ref)
            return pdf_content_combined, report_type
    
        if not folder.node_id:
            _logger.warning("La carpeta '%s' no tiene definido node_id. No se suben PDFs.", folder.name)
            return pdf_content_combined, report_type
    
        # 4) Itera sobre cada registro individualmente
        for rid in res_ids or []:
            # 4.1) Obtiene el registro actual
            Model = self.env[report.model]
            record = Model.browse(rid)
            if not record.exists():
                _logger.warning("El registro con ID %s no existe en %s. Se omite.", rid, report.model)
                continue
    
            # 4.2) Genera solo el PDF para este registro
            try:
                # Obtengo el XML ID de este action.report
                ext_id = self.env['ir.model.data'].search([
                    ('model', '=', 'ir.actions.report'),
                    ('res_id', '=', report.id)], limit=1).module + '.' + \
                    self.env['ir.model.data'].search([
                        ('model', '=', 'ir.actions.report'),
                        ('res_id', '=', report.id)], limit=1).name
                _logger.warning("Intentando hacer el pdf para la plantilla %s . Registo actual %s", ext_id,rid)
                pdf_content_single, _ = super()._render_qweb_pdf(
                    ext_id, res_ids=[rid], data=data, **kwargs)

            except Exception as e:
                _logger.error("Error generando PDF para %s ID=%s: %s", report.model, rid, e)
                continue
    
            # 4.3) Evalua el nombre de archivo usando print_report_name
            filename = self._evaluate_report_filename(report, record)
            if not filename:
                filename = f"{report_ref}_{rid}.pdf"
            _logger.debug("  -> Filename para ID %s: %s", rid, filename)
    
            # 4.4) Busca si ya existe en Alfresco
            try:
                node_id = self._find_existing_file(
                    url, user, pwd, filename, folder.node_id
                )
            except Exception as e_search:
                _logger.error("Error buscando '%s' en Alfresco: %s", filename, e_search)
                node_id = None
    
            # 4.5) Si existe: descarga, compara texto y actualiza si cambia. Si no existe: crea nuevo.
            if node_id:
                try:
                    existing_content = self._download_existing_content(url, user, pwd, node_id)
                    existing_text = self._extract_text_from_pdf(existing_content)
                    new_text = self._extract_text_from_pdf(pdf_content_single)
    
                    if existing_text != new_text:
                        self._update_existing_file(url, user, pwd, node_id, pdf_content_single, filename)
                        _logger.info("PDF actualizado en Alfresco: %s (node_id=%s)", filename, node_id)
                    else:
                        _logger.info("El contenido no cambio para '%s'. No se sube nueva version.", filename)
                except Exception as e_update:
                    _logger.error("Error actualizando '%s' (node_id=%s): %s", filename, node_id, e_update)
            else:
                try:
                    # Construir metadatos para este registro
                    _, metadata = self._build_metadata(report_ref, [rid])
                    _logger.info("Metadatos asociados al reporte: %s  | Diccionario: %s", rid, metadata)
                    self._upload_new_file(
                        url, user, pwd, folder.node_id,
                        filename, pdf_content_single, metadata
                    )
                    _logger.info("Nuevo PDF subido a Alfresco: %s", filename)
                except Exception as e_upload:
                    _logger.error("Error subiendo nuevo PDF '%s' a Alfresco: %s", filename, e_upload)
    
        # 5) Devuelve siempre el PDF combinado original
        return pdf_content_combined, report_type
        
    
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
        Construye los metadatos a partir de los campos definidos en metadata_field_ids.
        Cada campo es evaluado sobre el primer registro de res_ids.
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
    
        for field in report.metadata_field_ids:
            field_name = field.name
            value = getattr(record, field_name, None)
    
            if value is None:
                properties[field_name] = ""
            elif field.ttype in ['char', 'text', 'selection']:
                properties[field_name] = str(value)
            elif field.ttype == 'boolean':
                properties[field_name] = bool(value)
            elif field.ttype in ['integer', 'float', 'monetary']:
                properties[field_name] = float(value)
            elif field.ttype == 'date':
                properties[field_name] = value.isoformat() if value else ""
            elif field.ttype == 'datetime':
                properties[field_name] = value.isoformat() if value else ""
            elif field.ttype == 'many2one':
                # Usamos el nombre legible o el ID
                properties[field_name] = value.name or str(value.id)
            elif field.ttype == 'many2many':
                # Concatenar nombres o IDs separados por comas
                properties[field_name] = ', '.join(v.name or str(v.id) for v in value)
            else:
                # Tipo no controlado, usar string
                properties[field_name] = str(value)
    
        # También podemos agregar un timestamp de subida
        properties['fecha_subida'] = datetime.now().isoformat()
    
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

    @api.model
    def cron_export_reports_to_alfresco(self):
        """Imprime automáticamente todos los reportes con carpeta Alfresco asignada"""
        reports = self.search([('folder_id', '!=', False)])
        _logger.info("Ejecutando cron de exportación de reportes a Alfresco (%s reportes encontrados)", len(reports))

        for report in reports:
            model_name = report.model
            model = self.env[model_name]
            try:
                domain = safe_eval(report.record_domain or "[]")
            except Exception as e:
                _logger.error("Dominio inválido para el reporte %s: %s", report.name, e)
                domain = []

            records = model.search(domain)
            _logger.info("Procesando %s registros para el reporte %s", len(records), report.name)

            for record in records:
                try:
                    report._render_qweb_pdf(report.id, [record.id])
                    _logger.info("PDF generado para %s ID=%s", model_name, record.id)
                except Exception as e:
                    _logger.error("Error generando reporte %s para ID=%s: %s", model_name, record.id, e)
