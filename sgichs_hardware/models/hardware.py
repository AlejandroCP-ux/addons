# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class Hardware(models.Model):
    _name = 'it.asset.hardware'
    _description = 'Activo de Hardware'
    # COMENTARIO: Usamos _inherit para extender 'it.asset' del módulo core.
    _inherit = 'it.asset'

    # COMENTARIO: Este campo extiende la selección del modelo padre.
    # Odoo combina automáticamente las selecciones de los modelos heredados.
    type = fields.Selection(
        selection_add=[('hardware', 'Hardware')],
        ondelete={'hardware': 'cascade'}
    )

    subtype = fields.Selection(
        selection=[
            ('pc', 'PC'),
            ('laptop', 'Laptop'),
            ('server', 'Servidor'),
            ('mobile', 'Dispositivo Móvil'),
            ('other', 'Otro')
        ],
        string='Subtipo',
        required=True
    )
    inventory_number = fields.Char(string='Número de Inventario', unique=True)
    components_ids = fields.Many2many(
        'it.component',
        'hardware_component_rel',
        'hardware_id',
        'component_id',
        string='Componentes'
    )
    
    # Campos computados para control de módulos
    has_reporting_module = fields.Boolean(
        compute='_compute_module_status',
        compute_sudo=True,
        string='Tiene Módulo de Reportes?',
        help="Indica si el módulo de reportes está instalado"
    )
    has_network_module = fields.Boolean(
        compute='_compute_module_status',
        compute_sudo=True,
        string='Tiene Módulo de Red?'
    )
    has_software_module = fields.Boolean(
        compute='_compute_module_status',
        compute_sudo=True,
        string='Tiene Módulo de Software?'
    )
    software_ids = fields.Many2many(
    'it.asset.software',
    string="Software Instalado",
    compute='_compute_software_ids',
    store=False
    )

    # COMENTARIO: Los campos y la lógica para 'software_ids' y 'ip_ids' (y el ping)
    # han sido OMITIDOS intencionadamente. Serán añadidos por los módulos
    # 'sgich_software' y 'sgich_network' respectivamente, heredando este modelo.
    # Esto previene errores si esos módulos no están instalados.

    @api.model
    def create(self, vals):
        # Forzamos el tipo a 'hardware' en la creación.
        vals['type'] = 'hardware'
        return super(Hardware, self).create(vals)

    def write(self, vals):
        # Prevenimos que el tipo se cambie a algo que no sea 'hardware'.
        if 'type' in vals and vals['type'] != 'hardware':
            vals['type'] = 'hardware'
        return super(Hardware, self).write(vals)
    
    def _compute_software_ids(self):
        """Manejo seguro para campo que podría no existir"""
        for record in self:
            if 'software_ids' in record._fields:
                # Si el campo existe (módulo instalado), mantener valor
                record.software_ids = record.software_ids
            else:
                # Si no existe, devolver lista vacía
                record.software_ids = [(5, 0, 0)]
    
    
    @api.depends_context('modules')
    def _compute_module_status(self):
        """Calcula si los módulos dependientes están instalados"""
        modules = self.env['ir.module.module'].sudo()
        
        # Usamos búsqueda directa para mejor performance
        self.has_reporting_module = bool(modules.search_count([
            ('name', '=', 'sgichs_reporting'),
            ('state', '=', 'installed')
        ]))
        
        self.has_network_module = bool(modules.search_count([
            ('name', '=', 'sgichs_red'),
            ('state', '=', 'installed')
        ]))
        
        self.has_software_module = bool(modules.search_count([
            ('name', '=', 'sgichs_software'),
            ('state', '=', 'installed')
        ]))
    
    def action_manual_ping(self):
        """Manejo seguro para dependencias de módulos"""
        if not self.env['ir.module.module'].search([
            ('name', '=', 'sgichs_network'),
            ('state', '=', 'installed')
        ]):
            # Opción 1: Mostrar advertencia amigable
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Módulo requerido',
                    'message': 'Instale el módulo de redes para esta función',
                    'type': 'warning',
                }
            }
            # Opción 2: No hacer nada
            return False
            
        # Si el módulo está instalado, delegar la acción
        return self.env['network.service'].browse(self.ids).ping_action()
    
    
    def action_llamar_reporte_ficha_tecnica(self):
        self.ensure_one() 

        report_action_xml_id = 'test_sgichs.action_hardware_technical_sheet'

        # Obtener la acción del reporte y ejecutarla para el(los) registro(s) actual(es)
        try:
            report_action = self.env.ref(report_action_xml_id)
            if not report_action or report_action.report_type == '': # Comprobación simple
                _logger.error(f"No se pudo encontrar o no es válida la acción de reporte: {report_action_xml_id}")
            
                raise UserError(f"La acción de reporte '{report_action_xml_id}' no se encuentra o no es válida.")
                return False 
            return report_action.report_action(self)
        except ValueError as e:
        
            # raise UserError(f"Error al obtener la acción del reporte '{report_action_xml_id}': {e}")
            _logger.error(f"Error al intentar encontrar el XML ID '{report_action_xml_id}': {e}")
            return False # O un diccionario de error para el cliente