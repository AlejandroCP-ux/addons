import requests
import logging
import time 
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from requests.exceptions import RequestException

_logger = logging.getLogger(__name__)

class AlfrescoFolder(models.Model):
    _name = 'alfresco.folder'
    _description = 'Carpeta de Alfresco'
    _order = 'complete_path'

    name = fields.Char(string='Nombre', required=True)
    node_id = fields.Char(string='Node ID', required=True, index=True)
    parent_id = fields.Many2one('alfresco.folder', string='Carpeta Padre', ondelete='cascade', index=True)
    parent_left = fields.Integer(index=True)
    parent_right = fields.Integer(index=True) 
    complete_path = fields.Char(string='Ruta completa', compute='_compute_complete_path', store=True)
    child_ids = fields.One2many('alfresco.folder', 'parent_id', string='Subcarpetas')
    subfolder_count = fields.Integer(compute='_compute_counts', string='Subcarpetas')
 
    _sql_constraints = [
        ('unique_node_id', 'unique(node_id)', 'El Node ID debe ser unico.'),
        ('unique_complete_path', 'unique(complete_path)', 'La ruta completa debe ser unica.')
    ]

    @api.constrains('node_id')
    def _check_node_id(self):
        pass

    @api.depends('name', 'parent_id.complete_path')
    def _compute_complete_path(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_path = '/'.join(filter(None, [rec.parent_id.complete_path, rec.name]))
            else:
                rec.complete_path = f"/{rec.name}"

    @api.depends('child_ids')
    def _compute_counts(self):
        grouped = self.env['alfresco.folder'].read_group(
            [('parent_id', 'in', self.ids)],
            ['parent_id'],
            ['parent_id']
        )
        count_map = {group['parent_id'][0]: group['__count'] for group in grouped}
        for rec in self:
            rec.subfolder_count = count_map.get(rec.id, 0)

    def action_open_subfolders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Subcarpetas',
            'res_model': 'alfresco.folder',
            'view_mode': 'tree,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id},
        }

    def action_open_files(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Archivos',
            'res_model': 'alfresco.file',
            'view_mode': 'tree,form',
            'domain': [('folder_id', '=', self.id)],
            'context': {'default_folder_id': self.id},
        }

    @api.model
    def sync_from_alfresco(self):       
        config = self.env['ir.config_parameter'].sudo()
        repo_id = config.get_param('asi_alfresco_integration.alfresco_repo_id')
        if not repo_id:
            _logger.warning("No se encuentra configurado el 'alfresco_repo_id'.")
            return
    
        mapping_model = self.env['alfresco.report.mapping']
        try:
            start_time = time.time()
            alf_folders = mapping_model._recursive_folders(repo_id, repo_id)
        except Exception as e:
            _logger.error(f"Error al obtener carpetas desde Alfresco: {e}")
            return
    
        # Preparar estructuras
        alfresco_nodes = {node_id: path for node_id, path in alf_folders}
        odoo_folders = {rec.node_id: rec for rec in self.search([]) if rec.node_id}
    
        path_cache = {}  # path completo ? folder creado
        name_parent_cache = {}  # (nombre, parent_id) ? folder
    
        # Proceso de creación/actualizacion
        for node_id, path in sorted(alfresco_nodes.items(), key=lambda x: x[1].count('/')):
            segments = path.strip('/').split('/')
            parent = None
            current_path = ''
    
            for i, segment in enumerate(segments):
                current_path = f"{current_path}/{segment}"
                is_last = i == len(segments) - 1
    
                if current_path in path_cache:
                    parent = path_cache[current_path]
                    continue
    
                key = (segment, parent.id if parent else None)
                folder = name_parent_cache.get(key)
    
                if is_last:
                    # Si ya existe por node_id, verificamos si cambio de nombre o ubicacion
                    existing = odoo_folders.get(node_id)
                    if existing:
                        expected_path = f"{parent.complete_path}/{segment}" if parent else f"/{segment}"
                        if existing.complete_path != expected_path:
                            _logger.info(f"Renombrando/moviendo: {existing.complete_path} ? {expected_path}")
                            existing.sudo().write({
                                'name': segment,
                                'parent_id': parent.id if parent else False,
                            })
                        folder = existing
                    elif not folder:
                        folder = self.sudo().create({
                            'name': segment,
                            'node_id': node_id,
                            'parent_id': parent.id if parent else False,
                        })
                        _logger.info(f"Carpeta creada: {folder.complete_path}")
                else:
                    if not folder:
                        folder = self.sudo().search([
                            ('name', '=', segment),
                            ('parent_id', '=', parent.id if parent else False)
                        ], limit=1)
                        if not folder:
                            folder = self.sudo().create({
                                'name': segment,
                                'parent_id': parent.id if parent else False,
                            })
                            _logger.info(f"Carpeta intermedia creada: {folder.complete_path}")
    
                path_cache[current_path] = folder
                name_parent_cache[key] = folder
                parent = folder
    
        # Eliminar carpetas obsoletas (que no están en Alfresco)
        synced_node_ids = set(alfresco_nodes.keys())
        for node_id, record in odoo_folders.items():
            if node_id not in synced_node_ids:
                _logger.info(f"Eliminando carpeta obsoleta: {record.complete_path}")
                record.sudo().unlink()
    
        _logger.info(f"Sincronizacion completa en {time.time() - start_time:.2f}s")

