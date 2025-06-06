import requests
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)



class AlfrescoReportMapping(models.Model):
    _name = 'alfresco.report.mapping'
    _description = 'Relaciona un reporte de Odoo con su PDF en Alfresco'

    # El “modelo origen” y su registro
    res_model = fields.Char(string="Modelo Odoo", required=True, copy=False)
    res_id    = fields.Integer(string="ID del registro Odoo", required=True, copy=False)

    # Identificadores en Alfresco para la última versión subida
    version_series_id = fields.Char(string="Version Series ID", index=True, readonly=True)
    node_id           = fields.Char(string="Node ID (Alfresco)", index=True, readonly=True)

    # URL que apunta directamente al contenido binario de la última versión
    url               = fields.Char(string="URL de descarga", readonly=True)

    # Fecha/hora en que se subió o actualizó esa última versión
    last_update       = fields.Datetime(string="Última actualización", readonly=True)

    _sql_constraints = [
        ('unique_mapping', 'UNIQUE(res_model, res_id)', 'Ya existe un mapeo para este registro.'),
    ]


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
