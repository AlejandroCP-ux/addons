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


    def action_open_files(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Archivos',
            'res_model': 'alfresco.file',
            'view_mode': 'tree,form',
            'domain': [('folder_id', '=', self.id)],
            'context': {'default_folder_id': self.id},
        }
    
    def action_open_subfolders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Subcarpetas',
            'res_model': 'alfresco.folder',
            'view_mode': 'tree,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id},
        }
    

class AlfrescoReportMapping(models.Model):
    _name = 'alfresco.report.mapping'
    _description = 'Mapeo de reportes a carpetas Alfresco'

    report_id = fields.Many2one('ir.actions.report', string="Reporte", required=True)
    folder_selection = fields.Selection(
        string="Seleccionar Carpeta",
        selection=lambda self: self.env['alfresco.folder'].search([], order='complete_path').mapped(lambda r: (r.node_id, r.complete_path)),
        required=True
    )
    folder_node_id = fields.Char(
        compute='_compute_folder_info',
        store=True,
        string="ID de Carpeta en Alfresco",
        readonly=True
    )
    folder_name = fields.Char(
        compute='_compute_folder_info',
        store=True,
        string="Nombre de Carpeta",
        readonly=True
    )

    @api.onchange('report_id')
    def _onchange_report_id(self):
        self._set_folder_options()

    @api.depends('folder_selection')
    def _compute_folder_info(self):
        folders = dict(self.env['alfresco.folder'].search([], order='complete_path').mapped(lambda r: (r.node_id, r.complete_path)))
        for rec in self:
            if rec.folder_selection:
                rec.folder_node_id = rec.folder_selection
                rec.folder_name = folders.get(rec.folder_selection)
            else:
                rec.folder_node_id = False
                rec.folder_name = False

    def _set_folder_options(self):
        """
        Refresca las opciones del campo folder_selection desde el modelo local.
        """
        options = self.env['alfresco.folder'].search([], order='complete_path').mapped(lambda r: (r.node_id, r.complete_path))
        self._fields['folder_selection'].selection = options

    @api.model
    def _alfresco_get_children(self, repo_id, node_id, skip=0, max_items=100):
        RCS = self.env['ir.config_parameter'].sudo()
        url_base = RCS.get_param('asi_alfresco_integration.alfresco_server_url')
        user = RCS.get_param('asi_alfresco_integration.alfresco_username')
        pwd = RCS.get_param('asi_alfresco_integration.alfresco_password')

        endpoint = f"{url_base}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/children"
        params = {'include': 'isFolder','skipCount': skip,'maxItems': max_items}
        try:
            resp = requests.get(endpoint, auth=(user, pwd), params=params)
            resp.raise_for_status()
            data = resp.json().get('list', {})
            entries = data.get('entries', [])
            has_more = skip + max_items < data.get('pagination', {}).get('totalItems', 0)
            return entries, has_more
        except Exception as e:
            _logger.error("Error al obtener hijos de %s: %s", node_id, e)
            return [], False

    @api.model
    def _recursive_folders(self, repo_id, node_id, parent_path=''):
        """
        Recorre el árbol de carpetas y devuelve tuplas (node_id, ruta_completa).
        """
        folders = []
        skip = 0
        max_items = 100
        while True:
            entries, has_more = self._alfresco_get_children(repo_id, node_id, skip, max_items)
            for item in entries:
                entry = item.get('entry', {})
                if entry.get('isFolder'):
                    nid = entry.get('id')
                    name = entry.get('name')
                    path = f"{parent_path}/{name}" if parent_path else f"/{name}"
                    folders.append((nid, path))
                    # Recursea con la ruta actual
                    folders += self._recursive_folders(repo_id, nid, path)
            if not has_more:
                break
            skip += max_items
        return folders
