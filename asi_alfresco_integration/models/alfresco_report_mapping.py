import requests
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class AlfrescoReportMapping(models.Model):
    _name = 'alfresco.report.mapping'
    _description = 'Mapeo de reportes a carpetas Alfresco'

    report_id = fields.Many2one('ir.actions.report', string="Reporte", required=True)
    folder_selection = fields.Selection(string="Seleccionar Carpeta", selection='get_alfresco_folders', required=True)
    folder_node_id = fields.Char(compute='_compute_folder_info', store=True,string="ID de Carpeta en Alfresco", readonly=True)
    folder_name = fields.Char(compute='_compute_folder_info', store=True, string="Nombre de Carpeta", readonly=True)

    @api.onchange('report_id')
    def _onchange_report_id(self):
        self._set_folder_options()

    @api.depends('folder_selection')
    def _compute_folder_info(self):
        folders = dict(self.get_alfresco_folders())
        _logger.error("********************************* --------------Se ejecuta")
        for rec in self:
            if rec.folder_selection:
                rec.folder_node_id = rec.folder_selection
                rec.folder_name = folders.get(rec.folder_selection)
            else:
                rec.folder_node_id = False
                rec.folder_name = False
            
    @api.model  
    def get_alfresco_folders(self, parent_node_id=None):
        RCS = self.env['ir.config_parameter'].sudo()
        alfresco_server_url = RCS.get_param('asi_alfresco_integration.alfresco_server_url')
        alfresco_username = RCS.get_param('asi_alfresco_integration.alfresco_username')
        alfresco_password = RCS.get_param('asi_alfresco_integration.alfresco_password')
        alfresco_repo_id = RCS.get_param('asi_alfresco_integration.alfresco_repo_id')     
        if not  alfresco_server_url:
            _logger.error("No se encontró configuración de Alfresco.")
            return []

        parent_id = parent_node_id or alfresco_repo_id
        url = f"{alfresco_server_url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_id}/children"                               
        try:
            response = requests.get(url, auth=(alfresco_username, alfresco_password))
            _logger.error("********************************* --------------%s %s --> %s",alfresco_username, alfresco_password, response)
          
            response.raise_for_status()
            entries = response.json().get("list", {}).get("entries", [])

            folders = []
            for entry in entries:
                data = entry.get("entry", {})
                if data.get("isFolder"):
                    folders.append((data["id"], data["name"]))
            _logger.error("********************************* --------------%s ",folders)        
            return folders
        except Exception as e:
            _logger.error(f"Error al consultar carpetas de Alfresco: {e}")
            return []

    def _set_folder_options(self):
        folders = self.get_alfresco_folders()
        self._fields['folder_selection'].selection = folders
