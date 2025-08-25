# -*- coding: utf-8 -*-
import requests
import socket
import json
import logging
import random
from typing import Dict, Any, List, Optional
from .mapper import ComponentMapper # ¡Importamos el nuevo mapeador!

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(module)s] - %(message)s'
)

class ExportadorOdoo:
    def __init__(self, url_base: str, db: str, username: str, password: str):
        self.url_base = url_base.rstrip('/')
        self.db = db
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.uid = None
        self.software_module_installed = False
        self.network_module_installed = False
        self.mapper = ComponentMapper() # Instanciamos el mapeador
        self.modelos = {
            'backlog': 'it.asset.backlog',
            'componente': 'it.component',
            'software': 'it.asset.software',
            'ip': 'it.ip.address',
            'subtype': 'it.component.subtype',
            'module': 'ir.module.module'
        }

    def _autenticar(self) -> Optional[int]:
        # ... (código sin cambios)
        endpoint = f"{self.url_base}/web/session/authenticate"
        payload = {"jsonrpc": "2.0", "params": {"db": self.db, "login": self.username, "password": self.password}}
        try:
            response = self.session.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json().get('result')
            if result and result.get('uid'):
                self.uid = result['uid']
                logging.info(f"Autenticación exitosa - UID: {self.uid}")
                return self.uid
            logging.error(f"Autenticación fallida: {response.json().get('error')}")
            return None
        except Exception as e:
            logging.error(f"Error en autenticación: {e}")
            return None

    def _llamar_api(self, modelo: str, metodo: str, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Any:
        # ... (código sin cambios)
        if not self.uid and not self._autenticar(): return None
        url = f"{self.url_base}/web/dataset/call_kw"
        payload = {
            "jsonrpc": "2.0", "method": "call",
            "params": {"model": modelo, "method": metodo, "args": args or [], "kwargs": kwargs or {}},
            "id": random.randint(1, 1000000)
        }
        try:
            response = self.session.post(url, json=payload, timeout=20)
            response_data = response.json()
            if 'error' in response_data:
                logging.error(f"Error API Odoo: {response_data['error'].get('data', {}).get('message')}")
                return None
            return response_data.get('result')
        except Exception as e:
            logging.error(f"Error en llamada API: {e}")
            return None

    def check_installed_modules(self):
        # ... (código sin cambios)
        domain = [('state', '=', 'installed'), ('name', 'in', ['sgichs_software', 'sgichs_red'])]
        installed_modules = self._llamar_api('ir.module.module', 'search_read', [domain], {'fields': ['name']})
        if installed_modules is not None:
            module_names = {mod['name'] for mod in installed_modules}
            self.software_module_installed = 'sgichs_software' in module_names
            self.network_module_installed = 'sgichs_red' in module_names
        logging.info(f"Módulo Software: {'Instalado' if self.software_module_installed else 'No Instalado'}")
        logging.info(f"Módulo Red: {'Instalado' if self.network_module_installed else 'No Instalado'}")

    def _fetch_and_load_subtypes(self):
        """Obtiene todos los subtipos de Odoo y los carga en el mapeador."""
        logging.info("Obteniendo mapa de subtipos de componentes desde Odoo...")
        subtype_data = self._llamar_api(self.modelos['subtype'], 'search_read', [[]], {'fields': ['id', 'name']})
        if subtype_data:
            self.mapper.load_subtypes_from_odoo(subtype_data)
        else:
            logging.error("No se pudieron obtener los subtipos de componentes de Odoo.")

    def _buscar_o_crear(self, modelo: str, search_domain: list, create_vals: dict, update_vals: dict = None):
        # ... (código sin cambios)
        update_vals = update_vals or create_vals
        existente_ids = self._llamar_api(modelo, 'search', [search_domain], {'limit': 1})
        if existente_ids:
            record_id = existente_ids[0]
            self._llamar_api(modelo, 'write', [[record_id], update_vals])
            return record_id
        else:
            return self._llamar_api(modelo, 'create', [create_vals])

    def exportar_activo_completo(self, datos: Dict[str, Any]):
        if not self.uid:
            if not self._autenticar():
                logging.error("Exportación abortada. Se requiere autenticación.")
                return
        
        # ¡NUEVO! Obtenemos el mapa de subtipos antes de empezar a procesar
        self._fetch_and_load_subtypes()

        id_unico_hw = datos.get('placa_madre', {}).get('Número de Serie') or \
                      next((iface.get('mac') for iface in datos.get('red', []) if iface.get('mac')), None)
        if not id_unico_hw:
            logging.error("No se pudo determinar un ID único para el hardware. Abortando.")
            return

        # --- 1. PROCESAR Y CREAR COMPONENTES CON MAPEADOR ---
        component_ids = []
        todos_los_componentes = (datos.get('almacenamiento', []) + datos.get('ram', []) + 
                                 [datos.get('cpu', {})] + [datos.get('placa_madre', {})] + 
                                 datos.get('gpu', []) + datos.get('perifericos', []))

        for comp_data in todos_los_componentes:
            if not comp_data: continue
            
            # Usamos diferentes campos como número de serie de respaldo
            serial_number = comp_data.get('Número de Serie') or comp_data.get('ID único') or comp_data.get('id_unico') or comp_data.get('pnp_id')
            if not serial_number:
                continue
            
            # ¡NUEVO! Usamos el mapeador para obtener el subtype_id
            subtype_id = self.mapper.get_subtype_id(comp_data)
            if not subtype_id:
                logging.warning(f"Omitiendo componente sin subtipo mapeado: {comp_data.get('Modelo') or comp_data.get('nombre')}")
                continue

            comp_vals = {
                'model': comp_data.get('Modelo') or comp_data.get('nombre', 'Desconocido'),
                'serial_number': serial_number,
                'subtype_id': subtype_id
            }
            comp_id = self._buscar_o_crear(
                self.modelos['componente'],
                [('serial_number', '=', comp_vals['serial_number'])],
                comp_vals
            )
            if comp_id:
                component_ids.append(comp_id)

        # --- 2. PROCESAR IPs ---
        ip_ids = []
        if self.network_module_installed and 'red' in datos:
            for iface in datos['red']:
                for ip_addr in iface.get('ipv4', []):
                    ip_vals = {'address': ip_addr, 'description': iface.get('nombre')}
                    ip_id = self._buscar_o_crear(self.modelos['ip'], [('address', '=', ip_addr)], ip_vals)
                    if ip_id:
                        ip_ids.append(ip_id)
        
        # --- 3. PROCESAR SOFTWARE ---
        software_ids = []
        if self.software_module_installed and 'programas' in datos:
            for prog in datos['programas']:
                sw_vals = {'name': prog.get('nombre', 'Desconocido'), 'version': prog.get('version', 'N/A')}
                sw_id = self._buscar_o_crear(self.modelos['software'], [('name', '=', sw_vals['name']), ('version', '=', sw_vals['version'])], sw_vals)
                if sw_id:
                    software_ids.append(sw_id)

        # --- 4. VINCULACIÓN FINAL EN BACKLOG ---
        os_info = datos.get('sistema_operativo', {})
        backlog_vals = {
            'description': f"{socket.gethostname()} - {os_info.get('sistema', 'OS Desc.')}",
            'type': 'hardware',
            'raw_data': json.dumps(datos, indent=2, default=str),
            'components_ids': [(6, 0, list(set(component_ids)))],
            'software_ids': [(6, 0, software_ids)] if self.software_module_installed else False,
            'ip_ids': [(6, 0, ip_ids)] if self.network_module_installed else False,
        }
        
        backlog_vals = {k: v for k, v in backlog_vals.items() if v is not False}

        self._buscar_o_crear(
            self.modelos['backlog'],
            [('name', '=', id_unico_hw)],
            {'name': id_unico_hw, **backlog_vals},
            backlog_vals
        )
        logging.info(f"Proceso de exportación para '{id_unico_hw}' completado.")

    def test_connection_with_odoo(self) -> bool:
        if not self._autenticar(): return False
        try:
            if isinstance(self._llamar_api('ir.module.module', 'search_count', [[('state', '=', 'installed')]]), int): return True
        except Exception: pass
        return False