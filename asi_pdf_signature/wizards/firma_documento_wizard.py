from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import tempfile
import os
import logging
from datetime import datetime
from io import BytesIO
from PIL import Image
import binascii

# Importaciones para firma digital
try:
    from endesive import pdf
    from cryptography.hazmat.primitives.serialization import pkcs12
    HAS_ENDESIVE = True
except ImportError:
    HAS_ENDESIVE = False

# Verificar la versión de PyPDF2 y adaptar las importaciones
try:
    import PyPDF2
    PYPDF2_VERSION = PyPDF2.__version__
    
    # Para versiones más recientes (>=2.0.0)
    if hasattr(PyPDF2, 'PdfReader'):
        from PyPDF2 import PdfReader, PdfWriter
        NEW_PYPDF2 = True
    # Para versiones antiguas
    else:
        from PyPDF2 import PdfFileReader as PdfReader, PdfFileWriter as PdfWriter
        NEW_PYPDF2 = False
    
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    NEW_PYPDF2 = False

_logger = logging.getLogger(__name__)

class FirmaDocumentoWizard(models.TransientModel):
    _name = 'firma.documento.wizard'
    _description = 'Asistente para Firma Digital de Documentos'

    pdf_documento = fields.Binary(string='Documento PDF a Firmar', required=True)
    nombre_documento = fields.Char(string='Nombre del Documento')
    contrasena_firma = fields.Char(string='Contraseña del Certificado', required=True)
    mostrar_contrasena = fields.Boolean(string='Mostrar Contraseña', default=False)
    pdf_firmado = fields.Binary(string='Documento Firmado', readonly=True)
    estado = fields.Selection([
        ('borrador', 'Borrador'),
        ('firmado', 'Firmado'),
        ('error', 'Error')
    ], string='Estado', default='borrador', required=True)
    mensaje_error = fields.Text(string='Mensaje de Error', readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente"""
        res = super(FirmaDocumentoWizard, self).default_get(fields_list)
        # Verificar que el usuario tenga los requisitos para firmar
        if not self.env.user.tiene_requisitos_firma():
            raise UserError(_('Para firmar documentos, debe configurar su certificado digital y su imagen de firma en sus preferencias de usuario.'))
        
        # Asegurarse de que el estado inicial sea 'borrador'
        res['estado'] = 'borrador'
        return res
    
    def action_firmar_documento(self):
        """Acción para firmar digitalmente el documento PDF"""
        self.ensure_one()
        
        if not HAS_ENDESIVE or not HAS_PYPDF2:
            self.write({
                'estado': 'error',
                'mensaje_error': _('Las bibliotecas necesarias no están instaladas. Por favor, instale "endesive" y "PyPDF2".')
            })
            return self._recargar_wizard()
        
        if not self.pdf_documento:
            self.write({
                'estado': 'error',
                'mensaje_error': _('Debe subir un documento PDF para firmar.')
            })
            return self._recargar_wizard()
        
        if not self.contrasena_firma:
            self.write({
                'estado': 'error',
                'mensaje_error': _('Debe ingresar la contraseña de su certificado.')
            })
            return self._recargar_wizard()
            
        usuario = self.env.user
        if not usuario.certificado_firma or not usuario.imagen_firma:
            self.write({
                'estado': 'error',
                'mensaje_error': _('Debe configurar su certificado y su imagen de firma en sus preferencias de usuario.')
            })
            return self._recargar_wizard()
        
        try:
            # Decodificar el documento PDF
            pdf_contenido = base64.b64decode(self.pdf_documento)
            
            # Crear archivo temporal para el PDF original
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                temp_pdf.write(pdf_contenido)
                temp_pdf_path = temp_pdf.name
            
            # Preparar la imagen de la firma
            imagen_firma = base64.b64decode(usuario.imagen_firma)
            imagen = Image.open(BytesIO(imagen_firma))
            
            # Escalar la imagen para que no sea demasiado grande
            MAX_WIDTH, MAX_HEIGHT = 200, 100
            w, h = imagen.size
            if w > MAX_WIDTH or h > MAX_HEIGHT:
                ratio = min(MAX_WIDTH / w, MAX_HEIGHT / h)
                w, h = int(w * ratio), int(h * ratio)
                imagen = imagen.resize((w, h), Image.LANCZOS)
            
            # Guardar la imagen temporalmente en formato PNG
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_img:
                imagen.save(temp_img, format='PNG')
                temp_img_path = temp_img.name
            
            # Leer el PDF original para obtener las dimensiones de la última página
            with open(temp_pdf_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                num_paginas = len(pdf_reader.pages)
                last_page = pdf_reader.pages[-1]
                
                # Obtener las dimensiones de la página
                if hasattr(last_page, 'mediaBox'):
                    page_width = float(last_page.mediaBox.getWidth())
                    page_height = float(last_page.mediaBox.getHeight())
                else:
                    # Si no podemos obtener las dimensiones, usar tamaño carta por defecto
                    from reportlab.lib.pagesizes import letter
                    page_width, page_height = letter
            
            # Calcular las coordenadas para la imagen de la firma
            # Posicionar la imagen en la esquina inferior derecha
            x = page_width - w - 50  # Margen derecho de 50 puntos
            y = 50  # Margen inferior de 50 puntos
            
            try:
                # Cargar el certificado PKCS12
                certificado_data = base64.b64decode(usuario.certificado_firma)
                private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                    certificado_data,
                    self.contrasena_firma.encode('utf-8')
                )
                
                # Datos para la firma digital
                date = datetime.now()
                date_str = date.strftime("D:%Y%m%d%H%M%S+00'00'")
                
                # Configurar el diccionario para la firma digital según el ejemplo proporcionado
                dct = {
                    "aligned": 0,
                    "sigflags": 3,
                    "sigflagsft": 132,
                    "sigpage": num_paginas - 1,  # Última página (índice 0)
                    "sigbutton": True,
                    "sigfield": "Signature1",
                    "auto_sigfield": True,
                    "sigandcertify": True,
                    "signaturebox": (x, y, x + w, y + h),  # Coordenadas absolutas
                    #"signature": f"Firmado digitalmente por {usuario.name}", # Si se habilita este campo, se sobreescribe el campo de abajo
                    "signature_img": temp_img_path,  # Ruta a la imagen de la firma
                    "contact": usuario.email or '',
                    "location": usuario.company_id.city or '',
                    "signingdate": date_str,
                    "reason": "Firma Digital de Documento",
                }
                
                # Leer el PDF original
                with open(temp_pdf_path, 'rb') as f:
                    datau = f.read()
                
                # Firmar digitalmente el PDF
                datas = pdf.cms.sign(
                    datau,
                    dct,
                    private_key,
                    certificate,
                    additional_certificates,
                    'sha256'
                )
                
                # Guardar el PDF firmado digitalmente de manera incremental
                with tempfile.NamedTemporaryFile(delete=False, suffix='_firmado.pdf') as temp_final:
                    # Escribir el contenido original
                    temp_final.write(datau)
                    # Añadir la firma de manera incremental
                    temp_final.write(datas)
                    temp_final_path = temp_final.name
                
                # Leer el PDF final firmado
                with open(temp_final_path, 'rb') as f:
                    pdf_final_contenido = f.read()
                
                # Actualizar el campo con el PDF firmado y cambiar el estado a 'firmado'
                self.write({
                    'pdf_firmado': base64.b64encode(pdf_final_contenido),
                    'estado': 'firmado'
                })
                
                # Limpiar archivos temporales
                for path in [temp_pdf_path, temp_img_path, temp_final_path]:
                    try:
                        os.unlink(path)
                    except Exception as e:
                        _logger.error(f"Error al eliminar archivo temporal {path}: {e}")
                
                # Forzar la recarga del wizard para mostrar el estado 'firmado'
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'firma.documento.wizard',
                    'view_mode': 'form',
                    'res_id': self.id,
                    'views': [(False, 'form')],
                    'target': 'new',
                    'flags': {'mode': 'edit'},
                }
                
            except binascii.Error:
                self.write({
                    'estado': 'error',
                    'mensaje_error': _('Error al decodificar el certificado. Verifique que el archivo sea válido.')
                })
                return self._recargar_wizard()
            except Exception as e:
                self.write({
                    'estado': 'error',
                    'mensaje_error': _('Error en la contraseña o el certificado: %s') % str(e)
                })
                return self._recargar_wizard()
                
        except Exception as e:
            # Registrar el error y actualizarlo en el wizard
            _logger.error(f"Error al firmar el documento: {e}", exc_info=True)
            self.write({
                'estado': 'error',
                'mensaje_error': str(e)
            })
            return self._recargar_wizard()
    
    def _recargar_wizard(self):
        """Método auxiliar para recargar el wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'firma.documento.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'flags': {'mode': 'edit'},
        }
    
    def action_descargar_pdf(self):
        """Acción para descargar el PDF firmado"""
        self.ensure_one()
        if not self.pdf_firmado:
            raise UserError(_('No hay documento firmado para descargar.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/firma_digital/descargar_pdf?pdf_id={self.id}',
            'target': 'self',
        }
