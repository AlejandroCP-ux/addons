import requests
import logging
from odoo import models, fields, api, _
from requests.exceptions import RequestException

_logger = logging.getLogger(__name__)

class AlfrescoFolder(models.Model):
    _name = 'alfresco.folder'
    _description = 'Carpeta de Alfresco'
    _order = 'complete_path'

    name = fields.Char(string='Nombre', required=True)
    node_id = fields.Char(string='Node ID', required=True, index=True)
    parent_id = fields.Many2one('alfresco.folder', string='Carpeta Padre', ondelete='cascade')
    complete_path = fields.Char(string='Ruta completa', compute='_compute_complete_path', store=True)
    child_ids = fields.One2many('alfresco.folder', 'parent_id', string='Subcarpetas')
    file_ids = fields.One2many('alfresco.file', 'folder_id', string='Archivos')
    file_count = fields.Integer(compute="_compute_counts")
    subfolder_count = fields.Integer(compute="_compute_counts")

    @api.depends('name', 'parent_id.complete_path')
    def _compute_complete_path(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_path = f"{rec.parent_id.complete_path}/{rec.name}"
            else:
                rec.complete_path = f"/{rec.name}"

    def _compute_counts(self):
        for rec in self:
            rec.file_count = len(rec.file_ids)
            rec.subfolder_count = len(rec.child_ids)

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
        """
        Sincroniza todas las carpetas desde Alfresco, recreando la jerarquia.
        """
        config = self.env['ir.config_parameter'].sudo()
        repo_id = config.get_param('asi_alfresco_integration.alfresco_repo_id')
        if not repo_id:
            _logger.warning("No se encuentra configurado el 'alfresco_repo_id'.")
            return

        mapping_model = self.env['alfresco.report.mapping']
        try:
            alf_folders = mapping_model._recursive_folders(repo_id, repo_id)
        except Exception as e:
            _logger.error(f"Error al obtener carpetas desde Alfresco: {e}")
            return

        # Borrar carpetas existentes de forma segura
        self.search([])._cascade_delete()

        # Cache para evitar búsquedas repetidas
        path_cache = {}

        # Ordenar por profundidad (más padres antes que hijos)
        for node_id, path in sorted(alf_folders, key=lambda x: x[1].count('/')):
            segments = path.strip('/').split('/')
            parent = None
            current_path = ''
            for i, segment in enumerate(segments):
                current_path = f"{current_path}/{segment}"
                if current_path in path_cache:
                    parent = path_cache[current_path]
                    continue

                folder = self.sudo().search([('complete_path', '=', current_path)], limit=1)
                if not folder:
                    folder = self.sudo().create({
                        'name': segment,
                        'node_id': node_id if i == len(segments) - 1 else False,
                        'parent_id': parent.id if parent else False
                    })
                    _logger.info(f"Carpeta creada: {folder.complete_path}")
                path_cache[current_path] = folder
                parent = folder

    def _cascade_delete(self):
        """
        Borra carpetas en orden descendente para evitar errores de claves foraneas.
        """
        for folder in self.sudo().sorted(key=lambda r: len(r.complete_path or ''), reverse=True):
            _logger.info(f"Eliminando carpeta: {folder.complete_path}")
            folder.unlink()

    @api.model
    def sync_files_from_alfresco(self):
        """
        Sincroniza archivos desde Alfresco para cada carpeta registrada en Odoo.
        Evita duplicados y maneja errores de red.
        """
        config = self.env['ir.config_parameter'].sudo()
        base_url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')

        if not all([base_url, user, pwd]):
            _logger.warning("Faltan parametros de configuracion para la integracion con Alfresco.")
            return

        auth = (user, pwd)
        headers = {"Accept": "application/json"}
        AlfrescoFile = self.env['alfresco.file'].sudo()

        # Obtener node_ids ya sincronizados
        existing_node_ids = set(AlfrescoFile.search([]).mapped('node_id'))

        for folder in self.sudo().search([]):
            if not folder.node_id:
                _logger.warning(f"Carpeta sin node_id: {folder.name}")
                continue

            url = f"{base_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{folder.node_id}/children"

            try:
                response = requests.get(url, auth=auth, headers=headers, timeout=10)
                response.raise_for_status()
                entries = response.json().get("list", {}).get("entries", [])
            except RequestException as e:
                _logger.warning(f"Error de conexion al obtener archivos de '{folder.name}': {e}")
                continue
            except ValueError as e:
                _logger.warning(f"Error al parsear JSON para carpeta '{folder.name}': {e}")
                continue

            new_files_count = 0
            for entry in entries:
                node = entry.get("entry", {})
                if not node.get("isFile"):
                    continue

                node_id = node.get("id")
                if not node_id or node_id in existing_node_ids:
                    continue

                file_vals = {
                    "name": node.get("name", "Sin Nombre"),
                    "node_id": node_id,
                    "mimetype": node.get("content", {}).get("mimeType"),
                    "url": f"{base_url}/preview/s/{node_id}",
                    "folder_id": folder.id
                }

                AlfrescoFile.create(file_vals)
                existing_node_ids.add(node_id)
                new_files_count += 1

            _logger.info(f"Carpeta '{folder.name}' sincronizada con {new_files_count} archivo(s) nuevo(s).")
