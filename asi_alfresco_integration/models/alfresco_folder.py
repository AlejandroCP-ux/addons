import requests
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class AlfrescoFolder(models.Model):
    _name = 'alfresco.folder'
    _description = 'Carpeta de Alfresco'
    _order = 'complete_path'

    name = fields.Char(string='Nombre', required=True)
    node_id = fields.Char(string='Node ID', required=True, index=True)
    parent_id = fields.Many2one(
        'alfresco.folder', string='Carpeta Padre', ondelete='cascade'
    )
    complete_path = fields.Char(
        string='Ruta completa', compute='_compute_complete_path', store=True
    )
    child_ids = fields.One2many('alfresco.folder', 'parent_id', string='Subcarpetas')
    file_ids = fields.One2many('alfresco.file', 'folder_id', string='Archivos')
    file_count = fields.Integer(compute="_compute_counts")
    subfolder_count = fields.Integer(compute="_compute_counts")
    
    def _compute_counts(self):
        for rec in self:
            rec.file_count = len(rec.file_ids)
            rec.subfolder_count = len(rec.child_ids)



    @api.depends('name', 'parent_id.complete_path')
    def _compute_complete_path(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_path = f"{rec.parent_id.complete_path}/{rec.name}"
            else:
                rec.complete_path = f"/{rec.name}"
                
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
        Sincroniza todas las carpetas de Alfresco en el modelo local 'alfresco.folder'.
        """
        # Obtener estructura completa con rutas absolutas
        alf_folders = self.env['alfresco.report.mapping']._recursive_folders(
            self.env['ir.config_parameter'].sudo().get_param('asi_alfresco_integration.alfresco_repo_id'),
            self.env['ir.config_parameter'].sudo().get_param('asi_alfresco_integration.alfresco_repo_id')
        )
        # Borrar existentes
        self.search([])._cascade_delete()
        # Crear registros según ruta completa
        # Ordenar por profundidad para crear padres antes de hijos
        for node_id, path in sorted(alf_folders, key=lambda x: x[1].count('/')):
            segments = path.strip('/').split('/')
            parent = None
            current_path = ''
            for segment in segments:
                current_path = f"{current_path}/{segment}"
                folder = self.search([('complete_path', '=', current_path)], limit=1)
                if not folder:
                    folder = self.create({
                        'name': segment,
                        'node_id': node_id if current_path == path else False,
                        'parent_id': parent.id if parent else False
                    })
                parent = folder

    def _cascade_delete(self):
        """
        Borra carpetas en orden descendente para evitar errores de FK.
        """
        for folder in self.sorted(key=lambda r: len(r.complete_path), reverse=True):
            folder.unlink()

    @api.model
    def sync_files_from_alfresco(self):
        config = self.env['ir.config_parameter'].sudo()
        base_url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')

        if not base_url:
            _logger.warning("Falta configuración o mapeo para Alfresco.")
            return

        
        auth = (user, pwd)

        for folder in self.search([]):
            url = f"{base_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{folder.node_id}/children"
            response = requests.get(url, auth=auth)
            if response.status_code != 200:
                continue

            entries = response.json().get("list", {}).get("entries", [])
            for entry in entries:
                node = entry["entry"]
                if node["isFile"]:
                    if not self.env["alfresco.file"].search([("node_id", "=", node["id"])]):
                        self.env["alfresco.file"].create({
                            "name": node["name"],
                            "node_id": node["id"],
                            "mimetype": node.get("content", {}).get("mimeType"),
                            "url": f"{base_url}/preview/s/{node['id']}",
                            "folder_id": folder.id
                        })
