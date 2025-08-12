from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64

class SeleccionarArchivosWizard(models.TransientModel):
    _name = 'seleccionar.archivos.wizard'
    _description = 'Wizard para Seleccionar Archivos PDF'

    wizard_id = fields.Many2one('firma.documento.wizard', string='Wizard Principal', required=True)
    archivo_ids = fields.One2many('archivo.temporal', 'wizard_id', string='Archivos PDF')

    def action_agregar_archivos(self):
        """Agregar los archivos seleccionados al wizard principal"""
        self.ensure_one()
        
        if not self.archivo_ids:
            raise UserError(_('Debe seleccionar al menos un archivo PDF.'))
        
        archivos_agregados = 0
        
        for archivo in self.archivo_ids:
            if archivo.archivo_pdf and archivo.nombre_archivo:
                # Validar que sea PDF
                if not archivo.nombre_archivo.lower().endswith('.pdf'):
                    raise UserError(_('El archivo "%s" no es un PDF válido.') % archivo.nombre_archivo)
                
                # Crear el documento
                self.env['documento.firma'].create({
                    'wizard_id': self.wizard_id.id,
                    'nombre_documento': archivo.nombre_archivo,
                    'pdf_documento': archivo.archivo_pdf,
                })
                archivos_agregados += 1
        
        if archivos_agregados == 0:
            raise UserError(_('Debe seleccionar al menos un archivo PDF válido.'))
        
        return {
            'type': 'ir.actions.act_window_close',
        }


class ArchivoTemporal(models.TransientModel):
    _name = 'archivo.temporal'
    _description = 'Archivo Temporal para Selección'

    wizard_id = fields.Many2one('seleccionar.archivos.wizard', string='Wizard', required=True, ondelete='cascade')
    nombre_archivo = fields.Char(string='Nombre del Archivo')
    archivo_pdf = fields.Binary(string='Archivo PDF', attachment=False)
    tamaño_archivo = fields.Char(string='Tamaño', compute='_compute_tamaño_archivo')

    @api.depends('archivo_pdf')
    def _compute_tamaño_archivo(self):
        for record in self:
            if record.archivo_pdf:
                try:
                    size_bytes = len(base64.b64decode(record.archivo_pdf))
                    if size_bytes < 1024:
                        record.tamaño_archivo = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        record.tamaño_archivo = f"{size_bytes / 1024:.1f} KB"
                    else:
                        record.tamaño_archivo = f"{size_bytes / (1024 * 1024):.1f} MB"
                except:
                    record.tamaño_archivo = "N/A"
            else:
                record.tamaño_archivo = "N/A"
