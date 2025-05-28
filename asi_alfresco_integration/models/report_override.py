import logging
import requests
import re
import json
from odoo import models
from datetime import datetime
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
        
        filename = False
        metadata = {}
        properties = {}  # Inicializar propiedades
        
        ###################################Facturas#####################################################
        # 1. Verificar si es un reporte de factura (account.move)
        report = self._get_report(report_ref)
        if report.model == 'account.move' and res_ids:
            # 2. Obtener el registro de la factura
            invoice = self.env['account.move'].browse(res_ids[0])
            if invoice.exists():
                # 3. Usar el nombre de la factura y limpiar caracteres
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
        # Si no es factura o no se pudo obtener el nombre, usar nombre genérico
        if not filename:
            filename = f"{report_ref}_{'_'.join(map(str, res_ids or []))}.pdf"
        ################################################################################################
        
        try:
            # Intentar crear el documento por primera vez
            endpoint = (
                f"{url}/alfresco/api/-default-/public/"
                f"alfresco/versions/1/nodes/{mapping.folder_node_id}/children"
            )
            # ESPECIFICAR TIPO MIME Y ENCABEZADOS
            files = {'filedata': (filename, pdf_content, 'application/pdf')}
            params = {'autoRename': 'true'}
            json_data = {
                "name": filename,
                "nodeType": "cm:content",
                "properties": properties
            }
            resp = requests.post(
                endpoint,
                files=files,
                params=params,
                data={"json": json.dumps(json_data)},
                auth=(user, pwd),
                # AÑADIR ENCABEZADO EXPLÍCITO
                headers={'Content-Type': 'multipart/form-data'}
            )
            resp.raise_for_status()
            _logger.info(f"Documento creado: {filename}")
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                # Documento ya existe, actualizar versión
                try:
                    # Buscar el documento existente por nombre
                    list_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{mapping.folder_node_id}/children"
                    list_resp = requests.get(
                        list_url,
                        auth=(user, pwd),
                        headers={'Content-Type': 'application/json'}
                    )
                    list_resp.raise_for_status()
                    
                    # Buscar el documento por nombre
                    node_id = None
                    for entry in list_resp.json().get('list', {}).get('entries', []):
                        if entry['entry'].get('name') == filename:
                            node_id = entry['entry']['id']
                            break
                    
                    if not node_id:
                        _logger.error("Documento existente no encontrado para actualizar")
                        return pdf_content, report_type
                    
                    # Actualizar contenido del documento usando el endpoint específico
                    update_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
                    
                    # SOLUCIÓN AL ERROR 415 - ESPECIFICAR TIPO MIME Y ENCABEZADOS
                    update_resp = requests.put(
                        update_url,
                        files={'filedata': (filename, pdf_content, 'application/pdf')},
                        auth=(user, pwd),
                        # ENCABEZADO CRÍTICO PARA EVITAR ERROR 415
                        headers={'Content-Type': 'multipart/form-data'}
                    )
                    update_resp.raise_for_status()
                    
                    # Actualizar propiedades del documento
                    props_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}"
                    props_resp = requests.put(
                        props_url,
                        json={"properties": properties},
                        auth=(user, pwd),
                        headers={'Content-Type': 'application/json'}
                    )
                    props_resp.raise_for_status()
                    
                    _logger.info(f"Documento actualizado: {filename} (ID: {node_id})")
                    
                except requests.exceptions.HTTPError as update_http_error:
                    # Manejo específico de errores HTTP en actualización
                    if update_http_error.response.status_code == 415:
                        _logger.error("ERROR 415: Tipo de contenido no soportado")
                        _logger.error(f"URL: {update_url}")
                        _logger.error(f"Encabezados enviados: {update_http_error.request.headers}")
                        _logger.error(f"Respuesta de Alfresco: {update_http_error.response.text}")
                    else:
                        _logger.error(f"Error HTTP {update_http_error.response.status_code} actualizando documento: {update_http_error.response.text}")
                    
                except Exception as update_error:
                    _logger.error(f"**** Error actualizando documento existente: {update_error}")
                    
            else:
                # Manejar otros errores HTTP
                _logger.error(f"Error HTTP {e.response.status_code} subiendo PDF: {e.response.text}")
                
        except Exception as e:
            _logger.error(f"Error general subiendo PDF a Alfresco: {str(e)}")

        return pdf_content, report_type