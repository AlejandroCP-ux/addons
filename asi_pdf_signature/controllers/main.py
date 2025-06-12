from odoo import http
from odoo.http import request, content_disposition
import base64
import logging
import tempfile
import os
from io import BytesIO

_logger = logging.getLogger(__name__)

class FirmaDigitalController(http.Controller):
    
    @http.route('/firma_digital/descargar_pdf', type='http', auth='user')
    def descargar_pdf_firmado(self, pdf_id, **kwargs):
        """Controlador para descargar el PDF firmado"""
        try:
            # Obtener el registro del wizard temporal
            firma_wizard = request.env['firma.documento.wizard'].browse(int(pdf_id))
            
            if not firma_wizard.pdf_firmado:
                return request.not_found()
            
            # Obtener el nombre original del documento y añadir " - firmado"
            nombre_original = firma_wizard.nombre_documento or 'documento.pdf'
            nombre_base, extension = os.path.splitext(nombre_original)
            nombre_firmado = f"{nombre_base} - firmado{extension}"
            
            # Preparar la respuesta HTTP con el PDF
            pdf_content = base64.b64decode(firma_wizard.pdf_firmado)
            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', content_disposition(nombre_firmado))
            ]
            return request.make_response(pdf_content, headers=pdfhttpheaders)
            
        except Exception as e:
            _logger.error(f"Error al descargar el PDF firmado: {e}")
            return request.not_found()
