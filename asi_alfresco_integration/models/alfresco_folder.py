# models/alfresco_folder.py 

import requests
import base64
import logging
from odoo import models, fields, api, _  
from requests.auth import HTTPBasicAuth

_logger = logging.getLogger(__name__)

class AlfrescoFolder(models.Model):
    _name = 'alfresco.folder'
    _description = 'Carpeta Alfresco'
    _parent_name = "parent_id"

    name = fields.Char(required=True)
    node_id = fields.Char(required=True, help="ID de nodo en Alfresco", index=True)
    parent_id = fields.Many2one('alfresco.folder', string="Carpeta padre", ondelete='cascade')
    complete_path = fields.Char(string='Ruta completa', compute='_compute_complete_path', store=True)
    child_ids = fields.One2many('alfresco.folder', 'parent_id', string="Subcarpetas")
    subfolder_count = fields.Integer(compute='_compute_counts', string='Subcarpetas')
    
    @api.depends('child_ids')
    def _compute_counts(self): 
        for rec in self:
            rec.subfolder_count = len(rec.child_ids)

    def sync_from_alfresco(self):
        """Sincroniza esta carpeta y sus subcarpetas desde Alfresco"""
        config = self.env['res.config.settings'].get_values()
        base_url = config.get('alfresco_server_url')
        username = config.get('alfresco_username')
        password = config.get('alfresco_password')

        if not all([base_url, username, password]):
            _logger.error("Configuración de conexión a Alfresco incompleta.")
            return

        auth = HTTPBasicAuth(username, password)

        # Asegurarnos de recorrer cada carpeta por separado
        for folder in self:
            folder._sync_folder_recursive(base_url, auth)


    def _sync_folder_recursive(self, base_url, auth):
        """Sincroniza archivos y subcarpetas recursivamente"""
        self.ensure_one()
        _logger.info(f"[SYNC] Entrando a carpeta: '{self.name}' (Odoo ID: {self.id} – Node ID: {self.node_id})")

        # Primero sincronizamos los archivos de esta carpeta
        self._sync_files_in_folder(base_url, auth)

        # Ahora obtenemos todas las entradas (archivos y carpetas)
        url = (
            f"{base_url}/alfresco/api/-default-/public/alfresco/"
            f"versions/1/nodes/{self.node_id}/children?include=properties"
        )
        response = requests.get(url, auth=auth)
        if response.status_code != 200:
            _logger.error(f"[{self.name}] Error al obtener subcarpetas: {response.status_code}")
            return

        entries = response.json().get('list', {}).get('entries', [])

        for entry in entries:
            data = entry.get('entry', {})
            if not data.get('isFolder'):
                continue

            child_node_id = data.get('id')
            child_name    = data.get('name')

            # Buscamos si ya existe la carpeta en Odoo
            child = self.env['alfresco.folder'].search([
                ('node_id', '=', child_node_id)
            ], limit=1)

            if child:
                # Si ya existe, aseguramos que el parent_id esté bien
                if child.parent_id.id != self.id:
                    _logger.info(
                        f"[SYNC] Ajustando parent_id de '{child.name}' "
                        f"({child.id}) → nueva parent: {self.id}"
                    )
                    child.parent_id = self.id
            else:
                # Creamos la carpeta en Odoo
                _logger.info(
                    f"[SYNC] Creando carpeta en Odoo: '{child_name}' "
                    f"(Node ID: {child_node_id}, parent: {self.id})"
                )
                child = self.env['alfresco.folder'].create({
                    'name':       child_name,
                    'node_id':    child_node_id,
                    'parent_id':  self.id,
                })

            # Y finalmente bajamos recursivamente sus contenidos
            child._sync_folder_recursive(base_url, auth)


    def _sync_files_in_folder(self, base_url, auth):
        """Sincroniza archivos dentro de la carpeta actual"""
        url = (
            f"{base_url}/alfresco/api/-default-/public/alfresco/"
            f"versions/1/nodes/{self.node_id}/children?include=properties"
        )
        response = requests.get(url, auth=auth)
        if response.status_code != 200:
            _logger.error(f"[{self.name}] Error al obtener archivos: {response.status_code}")
            return

        entries = response.json().get('list', {}).get('entries', [])
        alfresco_file_ids = set()
        for entry in entries:
            data = entry.get('entry', {})
            if data.get('isFolder'):
                continue

            fid       = data.get('id')
            alfresco_file_ids.add(fid)
            name      = data.get('name')
            mime_type = data.get('content', {}).get('mimeType')
            size      = data.get('content', {}).get('sizeInBytes')
            mtime     = data.get('modifiedAt')

            existing = self.env['alfresco.file'].search(
                [('alfresco_node_id', '=', fid)], limit=1
            )
            # Si no cambió, salto
            if existing and existing.file_size == size and existing.modified_at == mtime:
                continue

            # Descargar y codificar
            resp = requests.get(
                f"{base_url}/alfresco/api/-default-/public/alfresco/"
                f"versions/1/nodes/{fid}/content", auth=auth
            )
            if resp.status_code != 200:
                _logger.warning(f"No se pudo descargar el archivo {name}")
                continue

            data_b64 = base64.b64encode(resp.content)

            vals = {
                'name':            name,
                'file_data':       data_b64,
                'alfresco_node_id': fid,
                'folder_id':       self.id,
                'mime_type':       mime_type,
                'file_size':       size,
                'modified_at':     mtime,
            }
            if existing:
                existing.write(vals)
                _logger.info(f"[SYNC] Archivo actualizado: {name}")
            else:
                self.env['alfresco.file'].create(vals)
                _logger.info(f"[SYNC] Archivo nuevo importado: {name}")

        # Borrar archivos que ya no existen en Alfresco
        for odoo_file in self.env['alfresco.file'].search([('folder_id', '=', self.id)]):
            if odoo_file.alfresco_node_id not in alfresco_file_ids:
                _logger.info(f"[SYNC] Eliminando obsoleto: {odoo_file.name}")
                odoo_file.unlink()


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
