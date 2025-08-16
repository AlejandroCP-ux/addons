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
    complete_path = fields.Char(string='Ruta completa', compute='_compute_complete_path', store=True, recursive=True)
    child_ids = fields.One2many('alfresco.folder', 'parent_id', string="Subcarpetas")
    subfolder_count = fields.Integer(compute='_compute_counts', string='Subcarpetas')
    file_count = fields.Integer(compute='_compute_counts', string='Archivos PDF')
    last_sync = fields.Datetime(string='Última sincronización')
    external_modified = fields.Datetime(string='Modificado en Alfresco')
    is_persistent = fields.Boolean(
        string='Carpeta Persistente', 
        default=True, 
        help="Las carpetas persistentes se mantienen en Odoo aunque no se encuentren temporalmente en Alfresco"
    )
    sync_status = fields.Selection([
        ('synced', 'Sincronizada'),
        ('missing', 'No encontrada en Alfresco'),
        ('error', 'Error de sincronización')
    ], string='Estado de Sincronización', default='synced')

    @api.depends('parent_id.complete_path', 'name')
    def _compute_complete_path(self):
        for rec in self:
            rec.complete_path = (rec.parent_id.complete_path or '/') + rec.name + '/'

    @api.depends('child_ids')
    def _compute_counts(self):
        for rec in self:
            rec.subfolder_count = len(rec.child_ids)
            rec.file_count = self.env['alfresco.file'].search_count([('folder_id', '=', rec.id)])

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

                    folder_rec = folder_map.get(nid)
                    if not folder_rec:
                        folder_rec = self.create({
                            'name': folder_data['name'],
                            'node_id': nid,
                            'parent_id': parent.id if parent else False,
                            'external_modified': parsed_modified,
                            'sync_status': 'synced',
                        })
                        folder_map[nid] = folder_rec
                        _logger.info("[SYNC] Nueva carpeta creada: %s (node_id: %s)", folder_data['name'], nid)
                    else:
                        # Actualizar nombre o fecha de modificación si han cambiado
                        if (folder_rec.name != folder_data['name'] or
                            folder_rec.parent_id != (parent if parent else False) or
                            folder_rec.external_modified != parsed_modified):
                            folder_rec.write({
                                'name': folder_data['name'],
                                'parent_id': parent.id if parent else False,
                                'external_modified': parsed_modified,
                            })
                            _logger.info("[SYNC] Carpeta actualizada: %s (node_id: %s)", folder_data['name'], nid)

                    folder_rec.last_sync = fields.Datetime.now()
                    # Agregar subcarpetas a la cola para procesamiento recursivo
                    queue.append((nid, folder_rec))
                    # Sincronizar archivos dentro de esta carpeta durante la sincronización global
                    self._sync_folder_files_only(folder_rec, url, auth)

            # CAMBIO PRINCIPAL: Solo eliminar carpetas que NO fueron encontradas en Alfresco
            self._clean_missing_folders(fetched_node_ids, folder_map)
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

    def _clean_missing_folders(self, fetched_ids, folder_map):
        """
        NUEVO: Solo elimina carpetas que definitivamente no existen en Alfresco
        Las carpetas persisten una vez sincronizadas, solo se eliminan si no se encuentran
        """
        missing_ids = set(folder_map.keys()) - fetched_ids
        if not missing_ids:
            _logger.info("[SYNC] Todas las carpetas sincronizadas siguen existiendo en Alfresco")
            return

        _logger.info("[SYNC] Verificando %d carpetas que no fueron encontradas en la sincronización actual", len(missing_ids))
        
        # Verificar individualmente cada carpeta "faltante" antes de eliminarla
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        confirmed_missing = []
        
        for node_id in missing_ids:
            folder_rec = folder_map[node_id]
            try:
                # Verificar directamente si la carpeta existe en Alfresco
                check_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}"
                response = requests.get(check_url, auth=(user, pwd), timeout=10)
                
                if response.status_code == 404:
                    # La carpeta definitivamente no existe
                    confirmed_missing.append(node_id)
                    _logger.warning("[SYNC] Carpeta confirmada como eliminada en Alfresco: %s (node_id: %s)", folder_rec.name, node_id)
                elif response.status_code == 200:
                    # La carpeta existe pero no fue encontrada en la sincronización (posible cambio de ubicación)
                    _logger.info("[SYNC] Carpeta existe en Alfresco pero cambió de ubicación: %s (node_id: %s)", folder_rec.name, node_id)
                    # Actualizar last_sync para indicar que sigue existiendo
                    folder_rec.last_sync = fields.Datetime.now()
                    folder_rec.sync_status = 'synced'
                else:
                    _logger.warning("[SYNC] No se pudo verificar el estado de la carpeta %s: HTTP %s", folder_rec.name, response.status_code)
                    
            except Exception as e:
                _logger.error("[SYNC] Error verificando carpeta %s: %s", folder_rec.name, e)
                folder_rec.sync_status = 'error'
        
        # Solo eliminar las carpetas confirmadas como faltantes
        if confirmed_missing:
            folders_to_delete = self.env['alfresco.folder'].browse(
                [folder_map[nid].id for nid in confirmed_missing]
            )
            
            # Eliminar archivos asociados antes de eliminar las carpetas
            file_model = self.env['alfresco.file']
            for folder in folders_to_delete:
                files = file_model.search([('folder_id', '=', folder.id)])
                if files:
                    files.unlink()
                    _logger.info("[SYNC] Eliminados %d archivos de la carpeta %s", len(files), folder.name)
            
            folders_to_delete.unlink()
            _logger.info("[SYNC] Eliminadas %d carpetas confirmadas como faltantes en Alfresco", len(folders_to_delete))
        else:
            _logger.info("[SYNC] No se eliminaron carpetas - todas siguen existiendo en Alfresco")

    def _sync_folder_content(self):
        """Sincroniza tanto subcarpetas como archivos de esta carpeta"""
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd]):
            return
        
        try:
            # Sincronizar subcarpetas
            folders_data = self._fetch_folder_batch(self._get_http_session(), url, (user, pwd), self.node_id)
            existing_subfolders_in_odoo = self.search([('parent_id', '=', self.id)])
            existing_subfolder_map = {f.node_id: f for f in existing_subfolders_in_odoo}
            fetched_subfolder_node_ids = set()

            if folders_data:
                for folder_data in folders_data:
                    nid = folder_data['id']
                    fetched_subfolder_node_ids.add(nid)
                    existing = existing_subfolder_map.get(nid)
                    raw_date = folder_data.get('modifiedAt')
                    parsed_modified = date_parser.parse(raw_date).replace(tzinfo=None) if raw_date else False
                    
                    if not existing:
                        self.create({
                            'name': folder_data['name'],
                            'node_id': nid,
                            'parent_id': self.id,
                            'external_modified': parsed_modified,
                            'last_sync': fields.Datetime.now(),
                            'sync_status': 'synced',
                        })
                        _logger.info("[SYNC] Nueva subcarpeta creada: %s en %s", folder_data['name'], self.name)
                    else:
                        # Update existing folder name/modified date if changed
                        if (existing.name != folder_data['name'] or
                            existing.external_modified != parsed_modified):
                            existing.write({
                                'name': folder_data['name'],
                                'external_modified': parsed_modified,
                            })
                        existing.last_sync = fields.Datetime.now()
                        existing.sync_status = 'synced'
            
            # CAMBIO: Verificar individualmente subcarpetas faltantes
            missing_subfolder_ids = set(existing_subfolder_map.keys()) - fetched_subfolder_node_ids
            if missing_subfolder_ids:
                _logger.info("[SYNC] Verificando %d subcarpetas faltantes en %s", len(missing_subfolder_ids), self.name)
                
                confirmed_missing_subfolders = []
                for node_id in missing_subfolder_ids:
                    try:
                        check_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}"
                        response = requests.get(check_url, auth=(user, pwd), timeout=10)
                        
                        if response.status_code == 404:
                            confirmed_missing_subfolders.append(node_id)
                            _logger.warning("[SYNC] Subcarpeta confirmada como eliminada: %s", existing_subfolder_map[node_id].name)
                        elif response.status_code == 200:
                            _logger.info("[SYNC] Subcarpeta existe pero cambió de ubicación: %s", existing_subfolder_map[node_id].name)
                            existing_subfolder_map[node_id].last_sync = fields.Datetime.now()
                            existing_subfolder_map[node_id].sync_status = 'synced'
                            
                    except Exception as e:
                        _logger.error("[SYNC] Error verificando subcarpeta: %s", e)
                        existing_subfolder_map[node_id].sync_status = 'error'
                
                if confirmed_missing_subfolders:
                    subfolders_to_delete = self.search([
                        ('parent_id', '=', self.id),
                        ('node_id', 'in', confirmed_missing_subfolders)
                    ])
                    
                    # Eliminar archivos asociados antes de eliminar subcarpetas
                    file_model = self.env['alfresco.file']
                    for subfolder in subfolders_to_delete:
                        files = file_model.search([('folder_id', '=', subfolder.id)])
                        files.unlink()
                    
                    subfolders_to_delete.unlink()
                    _logger.info("[SYNC] Eliminadas %d subcarpetas confirmadas como faltantes de %s", len(subfolders_to_delete), self.name)

            # Sincronizar archivos PDF (mantener lógica similar)
            files_data = self._fetch_folder_files(url, (user, pwd), self.node_id)
            file_model = self.env['alfresco.file']
            
            existing_files_in_odoo = file_model.search([('folder_id', '=', self.id)])
            existing_file_map = {f.alfresco_node_id: f for f in existing_files_in_odoo}
            fetched_file_node_ids = set()

            for file_data in files_data:
                nid = file_data['id']
                fetched_file_node_ids.add(nid)
                existing_file = existing_file_map.get(nid)
                
                raw_date = file_data.get('modifiedAt')
                parsed_modified = date_parser.parse(raw_date).replace(tzinfo=None) if raw_date else False
                
                file_vals = {
                    'name': file_data['name'],
                    'folder_id': self.id,
                    'alfresco_node_id': nid,
                    'mime_type': file_data.get('content', {}).get('mimeType', ''),
                    'file_size': file_data.get('content', {}).get('sizeInBytes', 0),
                    'modified_at': parsed_modified,
                }
                
                if existing_file:
                    # Update if name, size, or modified date changed
                    if (existing_file.name != file_vals['name'] or
                        existing_file.file_size != file_vals['file_size'] or
                        existing_file.modified_at != file_vals['modified_at']):
                        existing_file.write(file_vals)
                else:
                    file_model.create(file_vals)
            
            # Verificar archivos faltantes individualmente
            missing_file_ids = set(existing_file_map.keys()) - fetched_file_node_ids
            if missing_file_ids:
                _logger.info("[SYNC] Verificando %d archivos faltantes en %s", len(missing_file_ids), self.name)
                
                confirmed_missing_files = []
                for node_id in missing_file_ids:
                    try:
                        check_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}"
                        response = requests.get(check_url, auth=(user, pwd), timeout=10)
                        
                        if response.status_code == 404:
                            confirmed_missing_files.append(node_id)
                            _logger.warning("[SYNC] Archivo confirmado como eliminado: %s", existing_file_map[node_id].name)
                            
                    except Exception as e:
                        _logger.error("[SYNC] Error verificando archivo: %s", e)
                
                if confirmed_missing_files:
                    files_to_delete = file_model.search([
                        ('folder_id', '=', self.id),
                        ('alfresco_node_id', 'in', confirmed_missing_files)
                    ])
                    files_to_delete.unlink()
                    _logger.info("[SYNC] Eliminados %d archivos confirmados como faltantes de %s", len(files_to_delete), self.name)

            self.last_sync = fields.Datetime.now()
            self.sync_status = 'synced'
            
        except Exception as e:
            _logger.error("Error sincronizando contenido de carpeta %s: %s", self.name, e)
            self.sync_status = 'error'

    def _sync_folder_files_only(self, folder_rec, url, auth):
        """Sincroniza solo los archivos de una carpeta específica, usado en la sincronización global."""
        try:
            files_data = self._fetch_folder_files(url, auth, folder_rec.node_id)
            file_model = self.env['alfresco.file']
            
            existing_files_in_odoo = file_model.search([('folder_id', '=', folder_rec.id)])
            existing_file_map = {f.alfresco_node_id: f for f in existing_files_in_odoo}
            fetched_file_node_ids = set()

            for file_data in files_data:
                nid = file_data['id']
                fetched_file_node_ids.add(nid)
                existing_file = existing_file_map.get(nid)
                
                raw_date = file_data.get('modifiedAt')
                parsed_modified = date_parser.parse(raw_date).replace(tzinfo=None) if raw_date else False
                
                file_vals = {
                    'name': file_data['name'],
                    'folder_id': folder_rec.id,
                    'alfresco_node_id': nid,
                    'mime_type': file_data.get('content', {}).get('mimeType', ''),
                    'file_size': file_data.get('content', {}).get('sizeInBytes', 0),
                    'modified_at': parsed_modified,
                }
                
                if existing_file:
                    if (existing_file.name != file_vals['name'] or
                        existing_file.file_size != file_vals['file_size'] or
                        existing_file.modified_at != file_vals['modified_at']):
                        existing_file.write(file_vals)
                else:
                    file_model.create(file_vals)
            
            obsolete_file_ids = set(existing_file_map.keys()) - fetched_file_node_ids
            if obsolete_file_ids:
                files_to_delete = file_model.search([
                    ('folder_id', '=', folder_rec.id),
                    ('alfresco_node_id', 'in', list(obsolete_file_ids))
                ])
                files_to_delete.unlink()
                _logger.info("[SYNC] Eliminados %d archivos obsoletos de carpeta %s (global sync)", len(files_to_delete), folder_rec.name)

            folder_rec.last_sync = fields.Datetime.now()
            folder_rec.sync_status = 'synced'

        except Exception as e:
            _logger.error("Error sincronizando archivos de carpeta %s durante sync global: %s", folder_rec.name, e)
            folder_rec.sync_status = 'error'


    def _fetch_folder_files(self, base_url, auth, node_id):
        """Obtiene archivos PDF de un nodo específico en Alfresco - CORREGIDO"""
        session = self._get_http_session()
        try:
            encoded_node_id = urllib.parse.quote(node_id, safe='')
            url = f"{base_url.rstrip('/')}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{encoded_node_id}/children"
            
            # CORREGIDO: Buscar archivos PDF sin restricción de mimeType en la query
            params = {
                'skipCount': 0,
                'maxItems': 1000,
                'where': '(isFile=true)'  # Buscar todos los archivos primero
            }
            
            resp = session.get(url, auth=auth, params=params, timeout=30)
            
            # Si falla con público, probar privado
            if resp.status_code == 400:
                private_url = url.replace('/public/', '/private/')
                resp = session.get(private_url, auth=auth, params=params, timeout=30)
            
            resp.raise_for_status()
            
            data = resp.json()
            entries = data.get('list', {}).get('entries', [])
            
            # Filtrar PDFs en Python ya que el filtro de Alfresco puede fallar
            pdf_files = []
            for entry in entries:
                file_entry = entry['entry']
                content = file_entry.get('content', {})
                mime_type = content.get('mimeType', '')
                file_name = file_entry.get('name', '').lower()
                
                # Verificar si es PDF por MIME type o extensión
                if mime_type == 'application/pdf' or file_name.endswith('.pdf'):
                    pdf_files.append(file_entry)
                    _logger.info("PDF encontrado: %s (MIME: %s)", file_entry.get('name'), mime_type)
            
            _logger.info("Total PDFs encontrados en carpeta %s: %d", node_id, len(pdf_files))
            return pdf_files
            
        except Exception as e:
            _logger.error("Error obteniendo archivos del nodo %s: %s", node_id, e)
            return []
        finally:
            session.close()

    def action_view_content(self):
        """Ver contenido de esta carpeta (subcarpetas y archivos)"""
        self.ensure_one()
        
        # Sincronizar contenido si es necesario
        if not self.last_sync or (fields.Datetime.now() - self.last_sync).total_seconds() > 3600:
            try:
                self._sync_folder_content()
            except Exception as e:
                _logger.error("Error sincronizando contenido: %s", e)
        
        # Crear contexto para mostrar subcarpetas y archivos
        return {
            'type': 'ir.actions.act_window',
            'name': f'Contenido de: {self.name}',
            'view_mode': 'tree,form',
            'context': {
                'current_folder_id': self.id,
                'current_folder_name': self.name,
            },
            'target': 'current',
            'res_model': 'alfresco.folder',
            'domain': [('parent_id', '=', self.id)],
        }

    def action_view_files(self):
        """Ver archivos PDF de esta carpeta - CAMBIO: Tree primero"""
        self.ensure_one()
        
        # Sincronizar archivos si es necesario
        if not self.last_sync or (fields.Datetime.now() - self.last_sync).total_seconds() > 3600:
            try:
                self._sync_folder_content()
            except Exception as e:
                _logger.error("Error sincronizando contenido: %s", e)
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Archivos PDF - {self.name}',
            'res_model': 'alfresco.file',
            'view_mode': 'tree,kanban,form',  # CAMBIO: Tree primero, luego Kanban
            'domain': [('folder_id', '=', self.id)],
            'context': {
                'default_folder_id': self.id,
                'search_default_folder_id': self.id,
            },
        }

    def action_sync_folder(self):
        """Sincronizar esta carpeta y su contenido"""
        for folder in self:
            try:
                folder._sync_folder_content()
            except Exception as e:
                _logger.error("Error sincronizando carpeta %s: %s", folder.name, e)
                folder.sync_status = 'error'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def action_sync_all_folders(self):
        """Action to trigger a full synchronization of all Alfresco folders and files."""
        _logger.info("Manual trigger: Sincronizando todas las carpetas de Alfresco.")
        try:
            self.sync_from_alfresco() # Call the main cron sync method
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        except Exception as e:
            _logger.error("Error al iniciar sincronización global: %s", e)
            raise UserError(_("Error al iniciar sincronización global: %s") % str(e))

    def action_delete_from_alfresco(self):
        """
        NUEVO: Método específico para eliminar carpeta de Alfresco SOLO cuando el usuario lo solicite manualmente
        """
        self.ensure_one()
        
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd, self.node_id]):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Error: Configuración de Alfresco incompleta',
                    'type': 'danger',
                }
            }
        
        # Verificar si tiene subcarpetas o archivos
        if self.subfolder_count > 0 or self.file_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No se puede eliminar una carpeta que contiene subcarpetas o archivos. Elimine primero su contenido.',
                    'type': 'warning',
                }
            }
        
        try:
            # Eliminar carpeta de Alfresco usando la API REST
            delete_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{self.node_id}"
            response = requests.delete(delete_url, auth=(user, pwd), timeout=30)
            
            if response.status_code == 200:
                _logger.info(f"Carpeta {self.name} eliminada exitosamente de Alfresco")
                # Ahora eliminar el registro de Odoo
                super(AlfrescoFolder, self).unlink()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'Carpeta {self.name} eliminada correctamente de Alfresco y Odoo',
                        'type': 'success',
                    }
                }
            elif response.status_code == 404:
                _logger.warning(f"Carpeta {self.name} no encontrada en Alfresco (ya eliminada)")
                # Eliminar solo de Odoo
                super(AlfrescoFolder, self).unlink()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'Carpeta {self.name} no existía en Alfresco, eliminada solo de Odoo',
                        'type': 'warning',
                    }
                }
            else:
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error eliminando carpeta {self.name} de Alfresco: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error eliminando carpeta de Alfresco: {str(e)}',
                    'type': 'danger',
                }
            }

    def action_force_sync_folder(self):
        """Forzar sincronización de una carpeta específica, incluso si parece faltante"""
        self.ensure_one()
        
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd]):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Error: Configuración de Alfresco incompleta',
                    'type': 'danger',
                }
            }
        
        try:
            # Verificar si la carpeta existe en Alfresco
            check_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{self.node_id}"
            response = requests.get(check_url, auth=(user, pwd), timeout=10)
            
            if response.status_code == 200:
                # La carpeta existe, sincronizar su contenido
                self._sync_folder_content()
                self.write({
                    'sync_status': 'synced',
                    'last_sync': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'Carpeta {self.name} sincronizada exitosamente',
                        'type': 'success',
                    }
                }
            elif response.status_code == 404:
                # La carpeta no existe
                self.write({'sync_status': 'missing'})
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'La carpeta {self.name} no existe en Alfresco',
                        'type': 'warning',
                    }
                }
            else:
                response.raise_for_status()
                
        except Exception as e:
            _logger.error("Error en sincronización forzada de %s: %s", self.name, e)
            self.write({'sync_status': 'error'})
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Error sincronizando {self.name}: {str(e)}',
                    'type': 'danger',
                }
            }
