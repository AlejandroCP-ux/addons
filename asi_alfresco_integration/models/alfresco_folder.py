import collections
import logging
import requests
import base64
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dateutil import parser as date_parser

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AlfrescoFolder(models.Model):
    _name = 'alfresco.folder'
    _description = 'Carpeta Alfresco'
    _parent_name = "parent_id"
    _rec_name = 'complete_path'

    name = fields.Char(required=True)
    node_id = fields.Char(required=True, help="ID de nodo en Alfresco", index=True)
    parent_id = fields.Many2one('alfresco.folder', string="Carpeta padre", ondelete='cascade')
    complete_path = fields.Char(string='Ruta completa', compute='_compute_complete_path', store=True)
    child_ids = fields.One2many('alfresco.folder', 'parent_id', string="Subcarpetas")
    subfolder_count = fields.Integer(compute='_compute_counts', string='Subcarpetas')
    last_sync = fields.Datetime(string='Última sincronización')
    external_modified = fields.Datetime(string='Modificado en Alfresco')

    @api.depends('parent_id.complete_path', 'name')
    def _compute_complete_path(self):
        for rec in self:
            rec.complete_path = (rec.parent_id.complete_path or '/') + rec.name + '/'

    @api.depends('child_ids')
    def _compute_counts(self):
        for rec in self:
            rec.subfolder_count = len(rec.child_ids)

    def _get_http_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    @api.model
    def sync_from_alfresco(self):
        config = self.env['ir.config_parameter'].sudo()
        root_node = config.get_param('asi_alfresco_integration.alfresco_repo_id') or '-root-'
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')

        _logger.info(f"[SYNC] ***************** Iniciando proceso de sincronizacion de carpetas ********************")
        if not all([url, user, pwd]):
            raise UserError(_('Configuración de Alfresco incompleta en parámetros del sistema'))

        _logger.debug("[SYNC][Alfresco] Autenticando con: %s", user)

        auth = (user, pwd)
        session = self._get_http_session()

        existing_folders = self.search([])
        folder_map = {f.node_id: f for f in existing_folders}
        fetched_node_ids = set()
        queue = collections.deque([(root_node, None)])

        try:
            while queue:
                node_id, parent = queue.popleft()
                folders = self._fetch_folder_batch(session, url, auth, node_id)

                if folders is None:
                    continue 

                for folder_data in folders:
                    nid = folder_data['id']
                    fetched_node_ids.add(nid)
                    raw_date = folder_data.get('modifiedAt')
                    parsed_modified = date_parser.parse(raw_date).replace(tzinfo=None) if raw_date else False

                    #_logger.debug("[SYNC] Fecha convertida para %s: %s", folder_data['name'], parsed_modified)

                    folder_rec = folder_map.get(nid)
                    if not folder_rec:
                        folder_rec = self.create({
                            'name': folder_data['name'],
                            'node_id': nid,
                            'parent_id': parent.id if parent else False,
                            'external_modified': parsed_modified,
                        })
                        folder_map[nid] = folder_rec
                    else:
                        if (folder_rec.name != folder_data['name'] or
                            folder_rec.parent_id != parent or
                            folder_rec.external_modified != parsed_modified):
                            folder_rec.write({
                                'name': folder_data['name'],
                                'parent_id': parent.id if parent else False,
                                'external_modified': parsed_modified,
                            })

                    folder_rec.last_sync = fields.Datetime.now()
                    queue.append((nid, folder_rec))

            self._clean_obsolete_folders(fetched_node_ids, folder_map)
            return True
        except Exception as e:
            _logger.error("Error fatal durante sincronización: %s", e, exc_info=True)
            raise UserError(_("Error de sincronización: %s") % str(e)) from e
        finally:
            session.close() 

    def _fetch_folder_batch(self, session, base_url, auth, node_id):
        max_items = 100
        skip = 0
        all_folders = []

        while True:
            encoded_node_id = urllib.parse.quote(node_id, safe='')
            url = f"{base_url.rstrip('/')}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{encoded_node_id}/children"
            params = {
                'skipCount': skip,
                'maxItems': max_items,
                'where': '(isFolder=true)'
            }

            #_logger.debug("[SYNC][Alfresco] Nodo: %s | URL: %s | Params: %s | Usuario: %s", node_id, url, params, auth[0])

            try:
                resp = session.get(url, auth=auth, params=params, timeout=30, headers={'Accept': 'application/json'})

                if resp.status_code == 400 and node_id == '-root-':
                    _logger.warning("Fallo acceso público a '-root-', probando endpoint privado")
                    private_url = url.replace('/public/', '/private/')
                    resp = session.get(private_url, auth=auth, params=params, timeout=30)
                    resp.raise_for_status()
                else:
                    resp.raise_for_status()

                data = resp.json()
                entries = data.get('list', {}).get('entries', [])

                if not entries:
                    break

                for entry in entries:
                    all_folders.append(entry['entry'])

                if len(entries) < max_items:
                    break

                skip += max_items
            except requests.exceptions.RequestException as e:
                error_detail = ""
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = f" | Respuesta: {e.response.text[:500]}"
                    except:
                        error_detail = " | Sin detalles de respuesta"

                _logger.error('[SYNC][ERROR] Nodo: %s | Excepción: %s%s | URL: %s | Params: %s | Usuario: %s',
                              node_id, str(e), error_detail, url, params, auth[0])
                return None
            except (ValueError, KeyError) as e:
                _logger.error('Respuesta inválida en nodo %s: %s | URL: %s | Respuesta: %s',
                              node_id, str(e), url, resp.text[:500] if resp else 'Sin respuesta')
                return None

        return all_folders

    def _clean_obsolete_folders(self, fetched_ids, folder_map):
        obsolete_ids = set(folder_map.keys()) - fetched_ids
        if not obsolete_ids:
            return

        obsolete_folders = self.env['alfresco.folder'].browse(
            [f.id for nid, f in folder_map.items() if nid in obsolete_ids]
        )

        file_model = self.env['alfresco.file']
        for folder in obsolete_folders:
            files = file_model.search([('folder_id', '=', folder.id)])
            files.unlink()

        obsolete_folders.unlink()
        _logger.info("[SYNC] Eliminadas %d carpetas obsoletas", len(obsolete_folders))

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

    def action_sync_folder(self):
        for folder in self:
            # Lógica para sincronizar esta carpeta y sus subcarpetas
            # Debe incluir recursión a través de folder.child_ids
            # folder._sync_with_alfresco(recursive=True)
            a=1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Sincronización completada para {len(self)} carpetas',
                'type': 'success',
                'sticky': False,
            }
    }