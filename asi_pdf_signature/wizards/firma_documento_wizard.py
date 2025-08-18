from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import tempfile
import os
import logging
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import binascii
import zipfile

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

class DocumentSignatureTag(models.Model):
    _name = 'document.signature.tag'
    _description = 'Etiqueta de Firma'

    name = fields.Char(string="Nombre", required=True)


class DocumentoFirma(models.TransientModel):
    _name = 'documento.firma'
    _description = 'Documento para Firma'

    wizard_id = fields.Many2one('firma.documento.wizard', string='Wizard', required=True, ondelete='cascade')
    document_name = fields.Char(string='Nombre del Documento', required=True)
    pdf_document = fields.Binary(string='Documento PDF', required=True)
    pdf_signed = fields.Binary(string='Documento Firmado', readonly=True)
    signature_status = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('firmado', 'Firmado'),
        ('error', 'Error')
    ], string='Estado', default='pendiente')
    error_message = fields.Text(string='Error')
    document_size = fields.Char(string='Tamaño', compute='_compute_document_size')

    @api.depends('pdf_document')
    def _compute_document_size(self):
        for record in self:
            if record.pdf_document:
                try:
                    size_bytes = len(base64.b64decode(record.pdf_document))
                    if size_bytes < 1024:
                        record.document_size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        record.document_size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        record.document_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                except:
                    record.document_size = "N/A"
            else:
                record.document_size = "N/A"

    def action_descargar_individual(self):
        """Acción para descargar este documento individual"""
        self.ensure_one()
        if not self.pdf_signed:
            raise UserError(_('El documento no ha sido firmado.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/firma_digital/descargar_individual?documento_id={self.id}',
            'target': 'self',
        }


class FirmaDocumentoWizard(models.TransientModel):
    _name = 'firma.documento.wizard'
    _description = 'Asistente para Firma Digital de Documentos'

    # Campos para múltiples documentos
    document_ids = fields.One2many('documento.firma', 'wizard_id', string='Documentos a Firmar')
    document_count = fields.Integer(string='Cantidad de Documentos', compute='_compute_documento_count')
    
    # Campos específicos para la firma (copiados del módulo Alfresco)
    
    signature_role = fields.Many2one('document.signature.tag', string='Etiqueta de la firma', help='Rol con el que se desea firmar (ej: Aprobado por:, Entregado por:, etc.)', required=True, ondelete='cascade')
    # signature_role = fields.Char(string='Rol para la Firma', 
    #                       help='Rol con el que se desea firmar (ej: Aprobado por:, Entregado por:, etc.)')
    signature_password = fields.Char(string='Contraseña del Certificado')
    signature_position = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma', required=True, default='derecha',
       help='Posición en la parte inferior de la página donde se colocará la firma')
    
    # Campos adicionales para certificado e imagen en el wizard
    certificate_wizard = fields.Binary(string='Certificado (.p12) - Temporal', attachment=False,
                                      help='Certificado temporal para esta sesión de firma')
    certificate_wizard_name = fields.Char(string='Nombre del Certificado Temporal')
    wizard_signature_image = fields.Binary(string='Imagen de Firma - Temporal', attachment=False,
                                       help='Imagen temporal para esta sesión de firma')
    
    # Campos informativos sobre el state del user
    has_certificate = fields.Boolean(string='Usuario tiene certificado', compute='_compute_estado_usuario', store=False)
    has_password = fields.Boolean(string='Usuario tiene contraseña', compute='_compute_estado_usuario', store=False)
    has_image = fields.Boolean(string='Usuario tiene imagen', compute='_compute_estado_usuario', store=False)
    
    # Campos de state (copiados del módulo Alfresco)
    state = fields.Selection([
        ('borrador', 'Configuración'),
        ('procesando', 'Procesando'),
        ('completado', 'Completado'),
        ('error', 'Error')
    ], string='Estado', default='borrador', required=True)
    
    message_result = fields.Text(string='Resultado del Proceso', readonly=True)
    documents_processed = fields.Integer(string='Archivos Procesados', default=0)
    documents_with_error = fields.Integer(string='Archivos con Error', default=0)

    # Campos para descarga
    zip_signed = fields.Binary(string='ZIP con Documentos Firmados', readonly=True)
    zip_name = fields.Char(string='Nombre del ZIP', readonly=True)

    @api.depends('document_ids')
    def _compute_documento_count(self):
        for record in self:
            record.document_count = len(record.document_ids)
    
    @api.depends('certificate_wizard', 'certificate_wizard_name', 'wizard_signature_image')
    def _compute_estado_usuario(self):
        """Computa el state de configuración del user actual"""
        for record in self:
            try:
                # Valores por defecto
                record.has_certificate = False
                record.has_password = False
                record.has_image = False
                
                # Verificar que tenemos un user válido
                if not self.env.user:
                    continue
                    
                user = self.env.user
                
                # Verificar certificado de forma segura
                try:
                    if hasattr(user, 'certificado_firma'):
                        cert_value = getattr(user, 'certificado_firma', False)
                        if cert_value:
                            # Intentar decodificar para verificar que es válido
                            try:
                                cert_decoded = base64.b64decode(cert_value)
                                record.has_certificate = len(cert_decoded) > 0
                            except:
                                record.has_certificate = bool(cert_value)
                except Exception as e:
                    _logger.error(f"Error verificando certificado: {e}")
                    record.has_certificate = False
                
                # Verificar contraseña de forma segura
                try:
                    if hasattr(user, 'contrasena_certificado'):
                        pass_value = getattr(user, 'contrasena_certificado', False)
                        if pass_value:
                            record.has_password = bool(str(pass_value).strip())
                except Exception as e:
                    _logger.error(f"Error verificando contraseña: {e}")
                    record.has_password = False
                
                # Verificar imagen de forma segura
                try:
                    if hasattr(user, 'imagen_firma'):
                        img_value = getattr(user, 'imagen_firma', False)
                        if img_value:
                            # Intentar decodificar para verificar que es válida
                            try:
                                img_decoded = base64.b64decode(img_value)
                                record.has_image = len(img_decoded) > 0
                            except:
                                record.has_image = bool(img_value)
                except Exception as e:
                    _logger.error(f"Error verificando imagen: {e}")
                    record.has_image = False
                
            except Exception as e:
                _logger.error(f"ERROR GENERAL en _compute_estado_usuario: {e}")
                # Valores por defecto en caso de error
                record.has_certificate = False
                record.has_password = False
                record.has_image = False
    
    def action_seleccionar_archivos(self):
        """Acción para abrir un wizard de selección de archivos"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Seleccionar Archivos PDF',
            'res_model': 'seleccionar.archivos.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wizard_id': self.id,
            }
        }

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente"""
        res = super(FirmaDocumentoWizard, self).default_get(fields_list)
        
        # Asegurarse de que el state inicial sea 'borrador'
        res['state'] = 'borrador'
        
        return res

    def _obtener_datos_firma(self):
        """Obtiene los datos de firma priorizando wizard sobre user"""
        user = self.env.user
        
        # Priorizar certificado del wizard, sino usar el del user
        certificado_data = None
        if self.certificate_wizard:
            certificado_data = base64.b64decode(self.certificate_wizard)
        elif hasattr(user, 'certificado_firma') and user.certificado_firma:
            certificado_data = base64.b64decode(user.certificado_firma)
        
        if not certificado_data:
            raise UserError(_('Debe proporcionar un certificado .p12 en el wizard o tenerlo configurado en sus preferencias.'))
        
        # Priorizar imagen del wizard, sino usar la del user
        imagen_firma = None
        if self.wizard_signature_image:
            imagen_firma = self.wizard_signature_image
        elif hasattr(user, 'imagen_firma') and user.imagen_firma:
            imagen_firma = user.imagen_firma
        
        if not imagen_firma:
            raise UserError(_('Debe proporcionar una imagen de firma en el wizard o tenerla configurada en sus preferencias.'))
        
        # Priorizar contraseña del wizard, sino usar la del user
        contrasena = None
        if self.signature_password and self.signature_password.strip():
            contrasena = self.signature_password.strip()
        elif hasattr(user, 'contrasena_certificado') and user.contrasena_certificado:
            try:
                contrasena = user.get_contrasena_descifrada()
            except Exception as e:
                _logger.error(f"Error descifrando contraseña: {e}")
                contrasena = None
        
        if not contrasena:
            raise UserError(_('Debe proporcionar la contraseña del certificado.'))
        
        return certificado_data, imagen_firma, contrasena

    def _crear_imagen_firma_con_rol(self, imagen_firma_original, rol):
        """Crea una imagen de firma temporal con el texto del rol"""
        try:
            # Decodificar la imagen original
            imagen_data = base64.b64decode(imagen_firma_original)
            imagen = Image.open(BytesIO(imagen_data))
            
            # Convertir a RGBA si no lo está
            if imagen.mode != 'RGBA':
                imagen = imagen.convert('RGBA')
            
            # Dimensiones originales
            ancho_original, alto_original = imagen.size
            
            # Limitar ancho máximo a 205px manteniendo proporción
            max_ancho = 205
            if ancho_original > max_ancho:
                factor_escala = max_ancho / ancho_original
                nuevo_ancho_img = max_ancho
                nuevo_alto_img = int(alto_original * factor_escala)
                # Compatibilidad con versiones antiguas y nuevas de Pillow
                try:
                    # Para versiones nuevas de Pillow (>=8.0.0)
                    imagen = imagen.resize((nuevo_ancho_img, nuevo_alto_img), Image.Resampling.LANCZOS)
                except AttributeError:
                    # Para versiones antiguas de Pillow
                    imagen = imagen.resize((nuevo_ancho_img, nuevo_alto_img), Image.LANCZOS)
                ancho_original, alto_original = nuevo_ancho_img, nuevo_alto_img
            
            # Calcular nuevo alto (agregar espacio para el texto)
            try:
                # Intentar cargar una fuente del sistema
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except:
                try:
                    # Fuente alternativa
                    font = ImageFont.truetype("arial.ttf", 10)
                except:
                    # Fuente por defecto
                    font = ImageFont.load_default()
            
            # Texto a agregar
            texto = f"{rol}" if rol else ""
            
            if texto:
                # Calcular dimensiones del texto
                draw_temp = ImageDraw.Draw(imagen)
                bbox = draw_temp.textbbox((0, 0), texto, font=font)
                ancho_texto = bbox[2] - bbox[0]
                alto_texto = bbox[3] - bbox[1]
                
                # Crear nueva imagen con espacio adicional arriba
                margen_texto = 10
                nuevo_alto = alto_original + alto_texto + (margen_texto * 2)
                nuevo_ancho = max(ancho_original, ancho_texto + 20)
                
                # Crear imagen nueva con fondo transparente
                nueva_imagen = Image.new('RGBA', (nuevo_ancho, nuevo_alto), (255, 255, 255, 0))
                
                # Pegar el texto en la parte superior
                draw = ImageDraw.Draw(nueva_imagen)
                x_texto = (nuevo_ancho - ancho_texto) // 2  # Centrar texto
                y_texto = margen_texto
                draw.text((x_texto, y_texto), texto, fill=(0, 0, 0, 255), font=font)
                
                # Pegar la imagen original debajo del texto
                x_imagen = (nuevo_ancho - ancho_original) // 2  # Centrar imagen
                y_imagen = alto_texto + (margen_texto * 2)
                nueva_imagen.paste(imagen, (x_imagen, y_imagen), imagen if imagen.mode == 'RGBA' else None)
            else:
                nueva_imagen = imagen
            
            # Guardar en archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            nueva_imagen.save(temp_file, format='PNG')
            temp_file.close()
            
            return temp_file.name, nueva_imagen.size
            
        except Exception as e:
            _logger.error(f"Error creando imagen de firma con rol: {e}")
            raise UserError(_('Error al procesar la imagen de firma: %s') % str(e))

    def _calcular_coordenadas_firma(self, page_width, page_height, imagen_width, imagen_height, posicion):
        """Calcula las coordenadas de la firma según la posición seleccionada"""
        margen_inferior = 25
        margen_lateral = 1
        ancho = page_width / 4
        
        # Coordenada Y siempre en la parte inferior
        y = margen_inferior
        
        # Calcular coordenada X según la posición
        if posicion == 'izquierda':
            x = margen_lateral
        elif posicion == 'centro_izquierda':
            x = margen_lateral + ancho + 1
        elif posicion == 'centro_derecha':
            x = margen_lateral + ancho * 2 + 1
        else:  # derecha
            x = margen_lateral + ancho * 3 + 1
        
        x1 = x + ancho
        
        return x, y, x1

    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        self.ensure_one()
        
        # Validar bibliotecas necesarias
        if not HAS_ENDESIVE or not HAS_PYPDF2:
            self.write({
                'state': 'error',
                'message_result': _('Las bibliotecas necesarias no están instaladas. Por favor, instale "endesive" y "PyPDF2".')
            })
            return self._recargar_wizard()
        
        # Validar campos obligatorios
        if not self.document_ids:
            raise UserError(_('Debe seleccionar al menos un documento PDF para firmar.'))
        
        if not self.signature_role:
            raise UserError(_('Debe especificar el rol para la firma.'))
        
        # Cambiar state a procesando
        self.write({
            'state': 'procesando',
            'message_result': 'Iniciando proceso de firma...',
            'documents_processed': 0,
            'documents_with_error': 0
        })
        
        documents_processed = 0
        documents_with_error = 0
        errores_detalle = []
        
        try:
            # Obtener datos de firma (prioriza wizard sobre user)
            certificado_data, imagen_firma, contrasena = self._obtener_datos_firma()
            
            # Crear imagen de firma con rol
            imagen_firma_path, imagen_size = self._crear_imagen_firma_con_rol(
                imagen_firma, 
                self.signature_role
            )
            imagen_width, imagen_height = imagen_size
            
            # Cargar certificado
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                certificado_data,
                contrasena.encode('utf-8')
            )
            
            # Procesar cada documento
            for documento in self.document_ids:
                try:
                    self._firmar_documento_individual(
                        documento, imagen_firma_path, imagen_width, imagen_height,
                        private_key, certificate, additional_certificates
                    )
                    documento.signature_status = 'firmado'
                    documents_processed += 1
                    
                    # Actualizar progreso
                    self.write({
                        'documents_processed': documents_processed,
                        'message_result': f'Procesando... {documents_processed}/{len(self.document_ids)} archivos completados'
                    })
                    
                except Exception as e:
                    documents_with_error += 1
                    documento.signature_status = 'error'
                    documento.error_message = str(e)
                    error_msg = f"Error en {documento.document_name}: {str(e)}"
                    errores_detalle.append(error_msg)
                    _logger.error(f"Error firmando documento {documento.document_name}: {e}")
        
            # Limpiar archivo temporal
            try:
                os.unlink(imagen_firma_path)
            except:
                pass
        
            # Crear ZIP con documentos firmados
            self._crear_zip_firmados()
        
            # Preparar mensaje final
            if documents_with_error == 0:
                mensaje = f'✅ Proceso completado exitosamente!\n\n'
                mensaje += f'📄 {documents_processed} archivos firmados correctamente\n'
                mensaje += f'Puede descargar el archivo ZIP con todos los documentos firmados'
                estado_final = 'completado'
            else:
                mensaje = f'⚠️ Proceso completado con errores:\n\n'
                mensaje += f'✅ {documents_processed} archivos firmados correctamente\n'
                mensaje += f'❌ {documents_with_error} archivos con errores\n\n'
                if documents_processed > 0:
                    mensaje += 'Los archivos firmados exitosamente están disponibles para descarga.\n\n'
                mensaje += 'Errores detallados:\n' + '\n'.join(errores_detalle)
                estado_final = 'error' if documents_processed == 0 else 'completado'
        
            self.write({
                'state': estado_final,
                'message_result': mensaje,
                'documents_processed': documents_processed,
                'documents_with_error': documents_with_error
            })
        
        except Exception as e:
            _logger.error(f"Error general en proceso de firma: {e}")
            self.write({
                'state': 'error',
                'message_result': f'Error general: {str(e)}',
                'documents_with_error': len(self.document_ids)
            })
    
        return self._recargar_wizard()

    def _firmar_documento_individual(self, documento, imagen_firma_path, imagen_width, imagen_height,
                                   private_key, certificate, additional_certificates):
        """Firma un documento individual"""
        # Decodificar el documento PDF
        pdf_contenido = base64.b64decode(documento.pdf_document)
        
        # Crear archivo temporal para el PDF original
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf.write(pdf_contenido)
            temp_pdf_path = temp_pdf.name
        
        try:
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
            x, y, x1 = self._calcular_coordenadas_firma(
                page_width, page_height, imagen_width, imagen_height, self.signature_position
            )
            
            # Datos para la firma digital
            date = datetime.now()
            date_str = date.strftime("D:%Y%m%d%H%M%S+00'00'")
            
            # Configurar el diccionario para la firma digital
            dct = {
                "aligned": 0,
                "sigflags": 3,
                "sigflagsft": 132,
                "sigpage": num_paginas - 1,  # Última página (índice 0)
                "sigbutton": True,
                "sigfield": f"Signature_{documento.id}",
                "auto_sigfield": True,
                "sigandcertify": True,
                "signaturebox": (x, y, x1, y + imagen_height),
                "signature_img": imagen_firma_path,
                "contact": self.env.user.email or '',
                "location": self.env.user.company_id.city or '',
                "signingdate": date_str,
                "reason": f"Firma Digital - {self.signature_role}",
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
            
            # Actualizar el documento con el PDF firmado
            documento.pdf_signed = base64.b64encode(pdf_final_contenido)
            
            # Limpiar archivos temporales
            for path in [temp_pdf_path, temp_final_path]:
                try:
                    os.unlink(path)
                except Exception as e:
                    _logger.error(f"Error al eliminar archivo temporal {path}: {e}")
                    
        except Exception as e:
            # Limpiar archivo temporal en caso de error
            try:
                os.unlink(temp_pdf_path)
            except:
                pass
            raise e

    def _crear_zip_firmados(self):
        """Crea un archivo ZIP con todos los documentos firmados exitosamente"""
        documents_signed = self.document_ids.filtered(lambda d: d.signature_status == 'firmado' and d.pdf_signed)
        
        if not documents_signed:
            return
        
        # Crear archivo ZIP temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for documento in documents_signed:
                    # Obtener el nombre base y añadir " - firmado"
                    nombre_base, extension = os.path.splitext(documento.document_name)
                    nombre_firmado = f"{nombre_base} - firmado{extension}"
                    
                    # Añadir el PDF firmado al ZIP
                    pdf_content = base64.b64decode(documento.pdf_signed)
                    zip_file.writestr(nombre_firmado, pdf_content)
            
            temp_zip_path = temp_zip.name
        
        # Leer el ZIP y guardarlo en el campo
        with open(temp_zip_path, 'rb') as f:
            zip_content = f.read()
        
        # Generar nombre para el ZIP
        timestamp = datetime.now().strftime("%d.%m.%Y_%H.%M.%S")
        zip_name = f"Documentos_firmados_{timestamp}.zip"
        
        self.write({
            'zip_signed': base64.b64encode(zip_content),
            'zip_name': zip_name
        })
        
        # Limpiar archivo temporal
        try:
            os.unlink(temp_zip_path)
        except:
            pass

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
    
    def action_descargar_zip(self):
        """Acción para descargar el ZIP con documentos firmados"""
        self.ensure_one()
        if not self.zip_signed:
            raise UserError(_('No hay documentos firmados para descargar.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/firma_digital/descargar_zip?wizard_id={self.id}',
            'target': 'self',
        }

    def action_descargar_individual(self, documento_id):
        """Acción para descargar un documento individual"""
        documento = self.env['documento.firma'].browse(documento_id)
        if not documento.pdf_signed:
            raise UserError(_('El documento no ha sido firmado.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/firma_digital/descargar_individual?documento_id={documento_id}',
            'target': 'self',
        }
