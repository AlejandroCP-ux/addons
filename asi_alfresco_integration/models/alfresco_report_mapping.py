import requests
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AlfrescoReportMapping(models.Model):
    _name = 'alfresco.report.mapping'
    _description = 'Mapeo de reportes a carpetas Alfresco'

    report_id = fields.Many2one('ir.actions.report', string='Reporte')
    folder_id = fields.Many2one('alfresco.folder', string='Carpeta Alfresco')

    folder_name = fields.Char(string='Nombre de Carpeta', compute='_compute_folder_info', store=True)
    folder_node_id = fields.Char(string='ID de Carpeta', compute='_compute_folder_info', store=True)


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
