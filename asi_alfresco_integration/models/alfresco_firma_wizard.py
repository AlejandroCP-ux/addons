from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import tempfile
import os
import logging
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import requests
import traceback

# Importación adicional para manejo de claves
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import SignatureAlgorithmOID

_logger = logging.getLogger(__name__)

# Importaciones para firma digital
try:
    from endesive import signer
    from pypdf import PdfReader
    HAS_ENDESIVE = True
    HAS_PYPDF = True
    _logger.debug("Endesive y pypdf importados correctamente")
except ImportError as e:
    HAS_ENDESIVE = False
    HAS_PYPDF = False
    _logger.error("Error importando dependencias: %s", e)

class AlfrescoFirmaWizard(models.TransientModel):
    _name = 'alfresco.firma.wizard'
    _description = 'Asistente para Firma Digital de PDFs de Alfresco'

    # Campos para los archivos seleccionados
    file_ids = fields.Many2many('alfresco.file', string='Archivos PDF a Firmar')
    file_count = fields.Integer(string='Cantidad de Archivos', compute='_compute_file_count')
    
    # Campos específicos para la firma
    rol_firma = fields.Char(string='Rol para la Firma', 
                           help='Rol con el que se desea firmar (ej: Aporbado por:, Entregado por:, etc.)')
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
        res = super(AlfrescoFirmaWizard, self).default_get(fields_list)
        
        # Obtener archivos seleccionados del contexto
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model', '')
        
        if active_model == 'alfresco.file' and active_ids:
            # Filtrar solo archivos PDF válidos
            valid_files = self.env['alfresco.file'].browse(active_ids).filtered(
                lambda f: f.name.lower().endswith('.pdf') and f.alfresco_node_id
            )
            if valid_files:
                res['file_ids'] = [(6, 0, valid_files.ids)]
    
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
            
            # Limitar ancho máximo a 205px manteniendo proporción
            max_ancho = 205
            if ancho_original > max_ancho:
                factor_escala = max_ancho / ancho_original
                nuevo_ancho_img = max_ancho
                nuevo_alto_img = int(alto_original * factor_escala)
                imagen = imagen.resize((nuevo_ancho_img, nuevo_alto_img), Image.LANCZOS)
                ancho_original, alto_original = nuevo_ancho_img, nuevo_alto_img
            
            # Calcular nuevo alto (agregar espacio para el texto)
            font = self._obtener_fuente()
            
            # Texto a agregar
            texto = f"{rol}"
            
            # Calcular dimensiones del texto - Método moderno
            test_img = Image.new('RGB', (1, 1))
            draw_test = ImageDraw.Draw(test_img)
            bbox = draw_test.textbbox((0, 0), texto, font=font)
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
            x_texto = (nuevo_ancho - ancho_texto) // 2
            y_texto = margen_texto
            draw.text((x_texto, y_texto), texto, fill=(0, 0, 0, 255), font=font)
            
            # Pegar la imagen original debajo del texto
            x_imagen = (nuevo_ancho - ancho_original) // 2
            y_imagen = alto_texto + (margen_texto * 2)
            nueva_imagen.paste(imagen, (x_imagen, y_imagen), imagen)
            
            # Guardar en archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            nueva_imagen.save(temp_file, format='PNG')
            temp_file.close()
            
            return temp_file.name, nueva_imagen.size
            
        except Exception as e:
            _logger.error("Error creando imagen de firma con rol: %s", str(e), exc_info=True)
            raise UserError(_('Error al procesar la imagen de firma: %s') % str(e))
        
    def _obtener_fuente(self, tamano=10):
        """Obtiene la mejor fuente disponible con Pillow 11.3.0"""
        try:
            # Intentar fuentes comunes
            fuentes = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/Library/Fonts/Arial.ttf",  # macOS
                "C:\\Windows\\Fonts\\Arial.ttf"  # Windows
            ]
            
            for fuente in fuentes:
                try:
                    return ImageFont.truetype(fuente, tamano)
                except:
                    continue
            
            # Fuente por defecto si no se encuentra ninguna
            return ImageFont.load_default()
        except:
            return ImageFont.load_default()

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
        
        x1 = x + ancho
        
        return x, y, x1

    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        self.ensure_one()
        
        import pkg_resources
        pillow_version = pkg_resources.get_distribution("pillow").version
        pypdf_version = pkg_resources.get_distribution("pypdf").version
        _logger.debug(f"Versión de Pillow: {pillow_version}")
        _logger.debug(f"Versión de pypdf: {pypdf_version}")
        
        # Validar bibliotecas necesarias
        if not HAS_ENDESIVE or not HAS_PYPDF:
            self.write({
                'estado': 'error',
                'mensaje_resultado': _('Las bibliotecas necesarias no están instaladas. Por favor, instale "endesive" y "pypdf".')
            })
            return self._recargar_wizard()
        
        # Validar campos obligatorios
        if not self.contrasena_firma or not self.contrasena_firma.strip():
            raise UserError(_('Debe ingresar la contraseña del certificado.'))
        
        if not self.file_ids:
            raise UserError(_('Debe seleccionar al menos un archivo PDF para firmar.'))
        
        if not self.rol_firma or not self.rol_firma.strip():
            raise UserError(_('Debe especificar el rol para la firma.'))
        
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
            
            # Cargar certificado usando cryptography
            try:
                certificado_data = base64.b64decode(usuario.certificado_firma)
                private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                    certificado_data,
                    self.contrasena_firma.encode('utf-8')
                )
                
                # Asegurar que additional_certificates sea una lista
                if additional_certificates is None:
                    additional_certificates = []
                    
                _logger.debug("Certificado cargado correctamente")
                
            except Exception as e:
                raise UserError(_('Error al cargar el certificado: %s') % str(e))
            
            # CORRECCIÓN: Usar string para el algoritmo de hash
            hashalgo = 'sha256'  # Ahora es un string
            
            # Procesar cada archivo
            for archivo in self.file_ids:
                try:
                    self._firmar_archivo_individual(
                        archivo, imagen_firma_path, imagen_width, imagen_height,
                        private_key, certificate, additional_certificates,
                        hashalgo  # Pasar el algoritmo como string
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
                    _logger.error(f"Error firmando archivo {archivo.name}: {e}\n{traceback.format_exc()}")
        
            # Limpiar archivo temporal
            try:
                os.unlink(imagen_firma_path)
            except:
                pass
    
            # Preparar mensaje final
            if archivos_con_error == 0:
                mensaje = f'✅ Proceso completado exitosamente!\n\n'
                mensaje += f'📄 {archivos_procesados} archivos firmados correctamente\n'
                mensaje += f'Los documentos han sido actualizados con una nueva versión firmada en Alfresco'
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
            _logger.error(f"Error general en proceso de firma: {e}\n{traceback.format_exc()}")
            self.write({
                'estado': 'error',
                'mensaje_resultado': f'Error general: {str(e)}',
                'archivos_con_error': len(self.file_ids)
            })

        return self._recargar_wizard()

    def _firmar_archivo_individual(self, archivo, imagen_firma_path, imagen_width, imagen_height,
                                 private_key, certificate, additional_certificates, hashalgo):
        """Firma un archivo individual con pypdf 5.8.0"""
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
            # Leer PDF para obtener dimensiones usando pypdf 5.8.0
            with open(temp_pdf_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                num_paginas = len(pdf_reader.pages)
                last_page = pdf_reader.pages[-1]
                
                # Obtener dimensiones de la página - Método moderno
                try:
                    # pypdf 5.8.0: acceso directo y consistente a mediabox
                    page_width = float(last_page.mediabox.width)
                    page_height = float(last_page.mediabox.height)
                except Exception as dim_error:
                    _logger.warning("Error obteniendo dimensiones: %s. Usando tamaño carta", dim_error)
                    # Tamaño carta estándar (ANSI A: 8.5 × 11 pulgadas)
                    page_width = 612  # 8.5 * 72 puntos/pulgada
                    page_height = 792  # 11 * 72 puntos/pulgada
            
            # Calcular coordenadas según posición seleccionada
            x, y, x1 = self._calcular_coordenadas_firma(
                page_width, page_height, imagen_width, imagen_height, self.posicion_firma
            )
            
            # Configurar datos para la firma
            date = datetime.now()
            date_str = date.strftime("D:%Y%m%d%H%M%S+00'00'")
            
            dct = {
                "sigflags": 3,
                "contact": self.env.user.email or '',
                "location": self.env.user.company_id.city or '',
                "signingdate": date_str.encode('utf-8'),  # Debe ser bytes
                "reason": f"Firma Digital - {self.rol_firma}",
                "signature": f"Firmado por: {self.env.user.name}",
                "signaturebox": (x, y, x1, y + imagen_height),
                "signature_img": imagen_firma_path,
            }
            
            # Leer PDF original
            with open(temp_pdf_path, 'rb') as f:
                datau = f.read()
            
            # CORRECCIÓN: Detección mejorada de RSA-PSS
            pss = False
            if isinstance(private_key, rsa.RSAPrivateKey):
                # Verificar si el certificado usa RSA-PSS
                if hasattr(certificate, 'signature_algorithm_oid'):
                    pss = (certificate.signature_algorithm_oid == SignatureAlgorithmOID.RSASSA_PSS)
                    _logger.debug(f"Algoritmo de firma detectado: {certificate.signature_algorithm_oid}")
                else:
                    # Para versiones más antiguas de cryptography
                    signature_oid = certificate.signature_algorithm_oid._dotted_string
                    pss = (signature_oid == "1.2.840.113549.1.1.10")  # OID de RSA-PSS
                
                if pss:
                    _logger.debug("Usando RSA-PSS para firma")
                else:
                    _logger.debug("Usando PKCS#1 v1.5 para firma RSA")
            
            # Firmar digitalmente con endesive
            datas = signer.sign(
                datau,
                private_key,
                certificate,
                additional_certificates,
                hashalgo,  # String esperado
                attrs=True,
                pss=pss,  # Especificar si es RSA-PSS
                timestampurl=None
            )
            
            # Crear PDF firmado
            with tempfile.NamedTemporaryFile(delete=False, suffix='_firmado.pdf') as temp_final:
                temp_final.write(datau)
                temp_final.write(datas)
                temp_final_path = temp_final.name
            
            # Leer PDF firmado
            with open(temp_final_path, 'rb') as f:
                pdf_firmado_contenido = f.read()
            
            # Actualizar el archivo original con la versión firmada
            self._actualizar_version_firmada_alfresco(archivo, pdf_firmado_contenido)
            
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

    def _actualizar_version_firmada_alfresco(self, archivo_original, pdf_firmado_contenido):
        """
        Actualiza el archivo original en Alfresco con la versión firmada,
        creando una nueva versión del mismo documento
        """
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        # Usar la misma lógica que _update_existing_file en report_override.py
        update_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{archivo_original.alfresco_node_id}/content"
        
        try:
            response = requests.put(
                update_url,
                headers={"Content-Type": "application/pdf"},
                data=pdf_firmado_contenido,
                auth=(user, pwd),
                timeout=30
            )
            response.raise_for_status()
            
            # Actualizar el tamaño del archivo en Odoo
            archivo_original.write({
                'file_size': len(pdf_firmado_contenido),
                'modified_at': fields.Datetime.now(),
            })
            
            _logger.info(f"Archivo {archivo_original.name} actualizado con versión firmada en Alfresco")
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error actualizando archivo firmado en Alfresco: {e}")
            raise UserError(_('Error actualizando el archivo firmado en Alfresco: %s') % str(e))

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