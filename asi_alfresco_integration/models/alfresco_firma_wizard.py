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
import json
import requests # Importar requests aquí para la nueva función

_logger = logging.getLogger(__name__)
# Importaciones para firma digital
try:
    from endesive import pdf
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    from cryptography.x509 import load_der_x509_certificate
    import OpenSSL.crypto as crypto
    HAS_ENDESIVE = True
except ImportError:
    HAS_ENDESIVE = False

_logger.debug(f"TIENE ENDESIVE: {HAS_ENDESIVE}")
# Verificar la versión de PyPDF2 y adaptar las importaciones
try:
    import pypdf
    from pypdf import PdfReader, PdfWriter
    HAS_PYPDF = True
    
except ImportError:
    HAS_PYPDF = False

_logger.debug(f"TIENE PYPDF: {HAS_PYPDF}")

class AlfrescoFirmaWizard(models.TransientModel):
    _name = 'alfresco.firma.wizard'
    _description = 'Asistente para Firma Digital de PDFs de Alfresco'

    # Campos para los archivos seleccionados
    file_ids = fields.Many2many('alfresco.file', string='Archivos PDF a Firmar')
    file_count = fields.Integer(string='Cantidad de Archivos', compute='_compute_file_count')
    
    # Campos específicos para la firma
    # ELIMINADO: required=True del modelo, la validación se hace en action_firmar_documentos
    rol_firma = fields.Char(string='Rol para la Firma', 
                           help='Rol con el que se desea firmar (ej: Aporbado por:, Entregado por:, etc.)')
    # ELIMINADO: required=True del modelo, la validación se hace en action_firmar_documentos
    contrasena_firma = fields.Char(string='Contraseña del Certificado')
    posicion_firma = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma', required=True, default='derecha',
       help='Posición en la parte inferior de la página donde se colocará la firma')
    
    # Campos de estado
    estado = fields.Selection([
        ('borrador', 'Configuración'),
        ('procesando', 'Procesando'),
        ('completado', 'Completado'),
        ('error', 'Error')
    ], string='Estado', default='borrador', required=True)
    
    mensaje_resultado = fields.Text(string='Resultado del Proceso', readonly=True)
    archivos_procesados = fields.Integer(string='Archivos Procesados', default=0)
    archivos_con_error = fields.Integer(string='Archivos con Error', default=0)

    @api.depends('file_ids')
    def _compute_file_count(self):
        for record in self:
            record.file_count = len(record.file_ids)

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente"""
        res = super(AlfrescoFirmaWizard, self).default_get(fields_list)
        
        # Obtener archivos seleccionados del contexto
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            files = self.env['alfresco.file'].browse(active_ids)
            res['file_ids'] = [(6, 0, files.ids)]
        
        return res

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
            
            # NUEVO: Limitar ancho máximo a 205px manteniendo proporción
            max_ancho = 205
            if ancho_original > max_ancho:
                factor_escala = max_ancho / ancho_original
                nuevo_ancho_img = max_ancho
                nuevo_alto_img = int(alto_original * factor_escala - (max(ancho_original,nuevo_ancho_img)-min(ancho_original,nuevo_ancho_img)))
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
            texto = f"{rol}"
            
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
        ancho = page_width /4
        
        # Coordenada Y siempre en la parte inferior
        y = margen_inferior
        
        # Calcular coordenada X según la posición
        if posicion == 'izquierda':
            x = margen_lateral
        elif posicion == 'centro_izquierda':
            x = margen_lateral + ancho +1
        elif posicion == 'centro_derecha':
            x = margen_lateral + ancho*2 +1
        else:  # derecha
            x = margen_lateral + ancho*3 +1
        
        # Asegurar que no se salga de los márgenes
        x = max(margen_lateral, min(x, page_width - imagen_width - margen_lateral))
        x1 = x + ancho
        
        return x, y, x1

    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        self.ensure_one()
        
        # Validar bibliotecas necesarias
        if not HAS_ENDESIVE or not HAS_PYPDF:
            self.write({
                'estado': 'error',
                'mensaje_resultado': _('Las bibliotecas necesarias no están instaladas. Por favor, instale "endesive" y "pypdf".')
            })
            return self._recargar_wizard()
        
        # Validar campos obligatorios (ahora que no son required=True en el modelo)
        if not self.contrasena_firma or not self.contrasena_firma.strip():
            raise UserError(_('Debe ingresar la contraseña del certificado.'))
        
        if not self.file_ids:
            raise UserError(_('Debe seleccionar al menos un archivo PDF para firmar.'))
        
        if not self.rol_firma or not self.rol_firma.strip():
            raise UserError(_('Debe especificar el rol para la firma.'))
        
        # Validar requisitos del usuario (si el método existe)
        if hasattr(self.env.user, 'tiene_requisitos_firma') and not self.env.user.tiene_requisitos_firma():
            raise UserError(_('Para firmar documentos, debe configurar su certificado digital y su imagen de firma en sus preferencias de usuario.'))
        
        # Cambiar estado a procesando
        self.write({
            'estado': 'procesando',
            'mensaje_resultado': 'Iniciando proceso de firma...',
            'archivos_procesados': 0,
            'archivos_con_error': 0
        })
        
        usuario = self.env.user
        archivos_procesados = 0
        archivos_con_error = 0
        errores_detalle = []
        
        try:
            # Crear imagen de firma con rol
            imagen_firma_path, imagen_size = self._crear_imagen_firma_con_rol(
                usuario.imagen_firma, 
                self.rol_firma
            )
            imagen_width, imagen_height = imagen_size
            
            # Cargar certificado usando OpenSSL como alternativa
            certificado_data = base64.b64decode(usuario.certificado_firma)
            p12 = crypto.load_pkcs12(certificado_data, self.contrasena_firma.encode('utf-8'))
            
            # Convertir a formato compatible con endesive
            private_key = p12.get_privatekey().to_cryptography_key()
            certificate = p12.get_certificate().to_cryptography()
            additional_certificates = [cert.to_cryptography() for cert in p12.get_ca_certificates() or []]
            
            # Procesar cada archivo
            for archivo in self.file_ids:
                try:
                    self._firmar_archivo_individual(
                        archivo, imagen_firma_path, imagen_width, imagen_height,
                        private_key, certificate, additional_certificates
                    )
                    archivos_procesados += 1
                    
                    # Actualizar progreso
                    self.write({
                        'archivos_procesados': archivos_procesados,
                        'mensaje_resultado': f'Procesando... {archivos_procesados}/{len(self.file_ids)} archivos completados'
                    })
                    
                except Exception as e:
                    archivos_con_error += 1
                    error_msg = f"Error en {archivo.name}: {str(e)}"
                    errores_detalle.append(error_msg)
                    _logger.error(f"Error firmando archivo {archivo.name}: {e}")
        
        # Limpiar archivo temporal
            try:
                os.unlink(imagen_firma_path)
            except:
                pass
        
        # Preparar mensaje final
            if archivos_con_error == 0:
                mensaje = f'✅ Proceso completado exitosamente!\n\n'
                mensaje += f'📄 {archivos_procesados} archivos firmados correctamente\n'
                estado_final = 'completado'
            else:
                mensaje = f'⚠️ Proceso completado con errores:\n\n'
                mensaje += f'✅ {archivos_procesados} archivos firmados correctamente\n'
                mensaje += f'❌ {archivos_con_error} archivos con errores\n\n'
                mensaje += 'Errores detallados:\n' + '\n'.join(errores_detalle)
                estado_final = 'error'
        
            self.write({
                'estado': estado_final,
                'mensaje_resultado': mensaje,
                'archivos_procesados': archivos_procesados,
                'archivos_con_error': archivos_con_error
            })
        
        except Exception as e:
            _logger.error(f"Error general en proceso de firma: {e}")
            self.write({
                'estado': 'error',
                'mensaje_resultado': f'Error general: {str(e)}',
                'archivos_con_error': len(self.file_ids)
            })
    
        return self._recargar_wizard()

    def _firmar_archivo_individual(self, archivo, imagen_firma_path, imagen_width, imagen_height,
                                 private_key, certificate, additional_certificates):
        """Firma un archivo individual"""
        # Descargar el PDF desde Alfresco
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd]):
            raise UserError(_('Configuración de Alfresco incompleta'))
        
        # Descargar contenido del archivo
        download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{archivo.alfresco_node_id}/content"
        response = requests.get(download_url, auth=(user, pwd), timeout=30)
        response.raise_for_status()
        
        pdf_contenido = response.content
        
        # Crear archivo temporal para el PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf.write(pdf_contenido)
            temp_pdf_path = temp_pdf.name
        
        try:
            # Leer PDF para obtener dimensiones
            with open(temp_pdf_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                num_paginas = len(pdf_reader.pages)
                last_page = pdf_reader.pages[-1]
                
                # Obtener dimensiones de la página
                if hasattr(last_page, 'mediabox') and last_page.mediabox:
                    page_width = float(last_page.mediabox.width)
                    page_height = float(last_page.mediabox.height)
                else:
                    from reportlab.lib.pagesizes import letter
                    page_width, page_height = letter
            
            # Calcular coordenadas según posición seleccionada
            x, y, x1 = self._calcular_coordenadas_firma(
                page_width, page_height, imagen_width, imagen_height, self.posicion_firma
            )
            
            # Configurar datos para la firma
            date = datetime.now()
            date_str = date.strftime("D:%Y%m%d%H%M%S+00'00'")
            
            dct = {
                "aligned": 0,
                "sigflags": 3,
                "sigflagsft": 132,
                "sigpage": num_paginas - 1,
                "sigbutton": True,
                "sigfield": f"Signature_{archivo.id}",
                "auto_sigfield": True,
                "sigandcertify": True,
                "signaturebox": (x, y, x1, y + imagen_height),
                "signature_img": imagen_firma_path,
                "contact": self.env.user.email or '',
                "location": self.env.user.company_id.city or '',
                "signingdate": date_str,
                "reason": f"Firma Digital - {self.rol_firma}",
            }
            
            # Leer PDF original
            with open(temp_pdf_path, 'rb') as f:
                datau = f.read()
            
            # Firmar digitalmente
            datas = pdf.cms.sign(
                datau,
                dct,
                private_key,
                certificate,
                additional_certificates,
                'sha256'
            )
            
            # Crear PDF firmado
            with tempfile.NamedTemporaryFile(delete=False, suffix='_firmado.pdf') as temp_final:
                temp_final.write(datau)
                temp_final.write(datas)
                temp_final_path = temp_final.name
            
            # Leer PDF firmado
            with open(temp_final_path, 'rb') as f:
                pdf_firmado_contenido = f.read()
            
            # Subir PDF firmado de vuelta a Alfresco
            self._subir_pdf_firmado_alfresco(archivo, pdf_firmado_contenido)
            
            # Limpiar archivos temporales
            for path in [temp_pdf_path, temp_final_path]:
                try:
                    os.unlink(path)
                except:
                    pass
                    
        except Exception as e:
            # Limpiar archivo temporal en caso de error
            try:
                os.unlink(temp_pdf_path)
            except:
                pass
            raise e

    def _alfresco_file_exists_in_folder(self, url, user, pwd, folder_node_id, filename):
        """
        Verifica si un archivo con el nombre dado ya existe en la carpeta de Alfresco especificada.
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
        try:
            response = requests.post(
                search_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(query),
                auth=(user, pwd),
                timeout=10
            )
            response.raise_for_status()
            results = response.json().get('list', {}).get('entries', [])
            return bool(results)
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error verificando existencia de archivo en Alfresco para '{filename}' en carpeta '{folder_node_id}': {e}")
            return False # Asumir que no existe para no bloquear el proceso

    def _subir_pdf_firmado_alfresco(self, archivo_original, pdf_firmado_contenido):
        """Sube el PDF firmado de vuelta a Alfresco con nuevo formato de nombre"""
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        # Obtener nombre original sin extensión
        nombre_original = archivo_original.name
        nombre_base, extension = os.path.splitext(nombre_original)
        
        # Nuevo: Generar nombre con sufijo "_firmado" y número incremental si es necesario
        base_signed_name = f"{nombre_base}_firmado{extension}"
        nombre_firmado = base_signed_name
        counter = 0

        nombre_firmado = f"{nombre_base}_firmado{extension}"
        
        # Subir como nuevo archivo en la misma carpeta
        endpoint = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{archivo_original.folder_id.node_id}/children"
        files = {'filedata': (nombre_firmado, pdf_firmado_contenido)}
        data = {
            "json": json.dumps({
                "name": nombre_firmado,
                "nodeType": "cm:content",
                "properties": {
                    "cm:title": f"Documento firmado por {self.env.user.name}",
                    "cm:description": f"{self.rol_firma}"
                }
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
        
        # Crear registro en Odoo para el nuevo archivo
        response_data = response.json()
        nuevo_node_id = response_data['entry']['id']
        
        self.env['alfresco.file'].create({
            'name': nombre_firmado,
            'folder_id': archivo_original.folder_id.id,
            'alfresco_node_id': nuevo_node_id,
            'mime_type': 'application/pdf',
            'file_size': len(pdf_firmado_contenido),
            'modified_at': fields.Datetime.now(),
        })

    def _contar_firmas_digitales_pdf(self, pdf_contenido):
        """
        Este método ya no se usa para la lógica de nombres, pero se mantiene por si es necesario en el futuro.
        Cuenta las firmas digitales existentes en el contenido del PDF.
        """
        try:
            # Crear archivo temporal para leer el PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                temp_pdf.write(pdf_contenido)
                temp_pdf_path = temp_pdf.name
        
            try:
                # Leer PDF y contar firmas digitales
                with open(temp_pdf_path, 'rb') as f:
                    pdf_reader = PdfReader(f)
                
                    # Buscar firmas en el formulario AcroForm
                    if '/AcroForm' in pdf_reader.trailer.get('/Root', {}):
                        root = pdf_reader.trailer['/Root']
                        acro_form = root.get('/AcroForm', {})
                    
                        if '/Fields' in acro_form:
                            fields = acro_form['/Fields']
                            firma_count = 0
                        
                            # Iterar sobre los campos del formulario
                            for field_ref in fields:
                                field = field_ref.get_object()
                            
                                if field.get('/FT') == '/Sig' and field.get('/V'):
                                    # Campo de firma digital
                                    firma_count += 1
                        
                            return firma_count
                
                    # Si no hay AcroForm o no hay firmas
                    return 0
                
            finally:
                # Limpiar archivo temporal
                try:
                    os.unlink(temp_pdf_path)
                except:
                    pass
                
        except Exception as e:
            _logger.warning(f"Error contando firmas digitales en PDF: {e}")
            # En caso de error, retornar 0 para que sea la primera firma
            return 0

    def _recargar_wizard(self):
        """Método auxiliar para recargar el wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'alfresco.firma.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'flags': {'mode': 'edit'},
        }

    def action_cerrar_wizard(self):
        """Cerrar el wizard y refrescar la vista de archivos"""
        return {
            'type': 'ir.actions.act_window_close',
        }
