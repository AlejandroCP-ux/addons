# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, List, Optional

class ComponentMapper:
    """
    Clase responsable de mapear los datos de componentes recolectados a los
    subtipos de componentes configurados en Odoo.
    """
    def __init__(self):
        # Este diccionario almacenará los subtipos de Odoo: {'CPU': 1, 'RAM': 2, ...}
        self.subtype_map: Dict[str, int] = {}
        logging.info("Mapeador de Componentes inicializado.")

    def load_subtypes_from_odoo(self, subtype_data: List[Dict[str, Any]]):
        """
        Carga y procesa los datos de los subtipos obtenidos de Odoo.
        Odoo devuelve una lista de diccionarios, por ejemplo:
        [{'id': 1, 'name': 'CPU'}, {'id': 2, 'name': 'RAM'}, ...]
        """
        if not subtype_data:
            logging.warning("No se recibieron datos de subtipos desde Odoo. El mapeo no funcionará.")
            return

        # Creamos un mapa de búsqueda rápida: el nombre del subtipo en mayúsculas a su ID.
        self.subtype_map = {
            str(subtype['name']).upper().strip(): subtype['id']
            for subtype in subtype_data
        }
        logging.info(f"Cargados {len(self.subtype_map)} subtipos desde Odoo: {list(self.subtype_map.keys())}")

    def get_subtype_id(self, component_data: Dict[str, Any]) -> Optional[int]:
        """
        Determina el ID del subtipo para un componente dado, basándose en "pistas"
        en sus datos recolectados.
        """
        # --- Pistas para identificar el tipo de componente ---
        # Periféricos (tienen un campo 'tipo' explícito)
        if 'tipo' in component_data:
            tipo = str(component_data['tipo']).upper().strip()
            if tipo in self.subtype_map:
                return self.subtype_map[tipo]

        # Placa Madre
        if 'BIOS Fabricante' in component_data:
            return self.subtype_map.get('PLACA MADRE')

        # CPU
        if 'Núcleos físicos' in component_data:
            return self.subtype_map.get('CPU')

        # RAM (identificado por tener 'Banco' o 'Slot')
        if 'Banco' in component_data or 'Slot' in component_data:
            return self.subtype_map.get('RAM')

        # GPU
        if 'Driver versión' in component_data:
            return self.subtype_map.get('GPU')

        # Discos de Almacenamiento
        if 'Tipo interfaz' in component_data:
            if 'SSD' in component_data.get('Tipo', '').upper():
                return self.subtype_map.get('SSD')
            else:
                return self.subtype_map.get('DISCO DURO')

        # Si no se encuentra ninguna pista, se devuelve None.
        logging.warning(f"No se pudo determinar el subtipo para el componente: {component_data.get('Modelo')}")
        return None