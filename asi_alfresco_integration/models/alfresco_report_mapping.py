import requests
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class AlfrescoReportMapping(models.Model):
    _name = 'alfresco.report.mapping'
    _description = 'Mapeo de reportes a carpetas Alfresco'

    report_id = fields.Many2one('ir.actions.report', string="Reporte", required=True)
    folder_selection = fields.Selection(string="Seleccionar Carpeta", selection=[], required=True)
    folder_node_id = fields.Char(string="ID de Carpeta en Alfresco", readonly=True)
    folder_name = fields.Char(string="Nombre de Carpeta", readonly=True)

    @api.onchange('report_id')
    def _onchange_report_id(self):
        self._set_folder_options()

    @api.onchange('folder_selection')
    def _onchange_folder_selection(self):
        folders = self.get_alfresco_folders()
        folder_dict = dict(folders)
        if self.folder_selection:
            self.folder_node_id = self.folder_selection
            self.folder_name = folder_dict.get(self.folder_selection)

    def get_alfresco_folders(self, parent_node_id=None):
        config = self.env['alfresco.config'].search([], limit=1)
        if not config:
            _logger.error("No se encontró configuración de Alfresco.")
            return []

        parent_id = parent_node_id or config.repo_id
        url = f"{config.server_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_id}/children"

        try:
            response = requests.get(url, auth=(config.username, config.password))
            response.raise_for_status()
            entries = response.json().get("list", {}).get("entries", [])

            folders = []
            for entry in entries:
                data = entry.get("entry", {})
                if data.get("isFolder"):
                    folders.append((data["id"], data["name"]))
            return folders
        except Exception as e:
            _logger.error(f"Error al consultar carpetas de Alfresco: {e}")
            return []

    def _set_folder_options(self):
        folders = self.get_alfresco_folders()
        self._fields['folder_selection'].selection = folders
