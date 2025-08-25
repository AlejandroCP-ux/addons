# -*- coding: utf-8 -*-
import time
import logging
import sys
import os
from datetime import datetime
import keyring  # Importamos la librería

# Definimos el mismo nombre de servicio que en la GUI
KEYRING_SERVICE_NAME = "sgich-scan-agent"

# --- Configuración del Logging ---
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Agente] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Importación de los módulos del proyecto ---
try:
    from scan.core.exportador import ExportadorOdoo
    from scan.core.recolector import GestorTI
except ImportError as e:
    logging.error(f"Error de importación: {e}. Asegúrate de ejecutar desde la raíz del proyecto.")
    sys.exit(1)

class AgenteScanner:
    def __init__(self, config: dict):
        self.intervalo_principal_seg = config.get("intervalo_principal_min", 30) * 60
        self.intervalo_reintento_seg = config.get("intervalo_reintento_min", 5) * 60
        self.odoo_config = config.get("odoo_config")
        if not self.odoo_config:
            raise ValueError("La configuración de Odoo no se encontró.")
        
        # --- LÓGICA DE KEYRING ---
        username = self.odoo_config.get('username')
        if not username:
            raise ValueError("El nombre de usuario no se encontró en la configuración.")
        
        # Recuperamos la contraseña de forma segura desde el gestor del SO
        password = keyring.get_password(KEYRING_SERVICE_NAME, username)
        if not password:
            raise ValueError(f"No se encontró una contraseña guardada para el usuario '{username}'. "
                             "Por favor, ejecute el agente con el argumento '--config' para configurarla.")

        self.exportador = ExportadorOdoo(
            url_base=self.odoo_config.get('url'),
            db=self.odoo_config.get('db'),
            username=username,
            password=password  # Usamos la contraseña recuperada de forma segura
        )

    def _ejecutar_ciclo(self) -> bool:
        logging.info("Iniciando nuevo ciclo de escaneo...")
        if not self.exportador.test_connection_with_odoo():
            logging.error("La prueba de conexión inicial falló.")
            return False
        
        # ¡NUEVO! Comprobamos los módulos instalados en Odoo
        self.exportador.check_installed_modules()
        
        try:
            # Pasamos la información de los módulos al recolector
            gestor = GestorTI(
                software_installed=self.exportador.software_module_installed,
                network_installed=self.exportador.network_module_installed
            )
            datos_completos = gestor.recolectar_todo()
            self.exportador.exportar_activo_completo(datos_completos)
            logging.info("Ciclo de escaneo y exportación completado exitosamente.")
            return True
        except Exception as e:
            logging.error(f"Ocurrió un error durante el proceso de escaneo/exportación: {e}", exc_info=True)
            return False

    def iniciar(self):
        logging.info("Agente de escaneo iniciado. Primer escaneo en breve...")
        while True:
            exitoso = self._ejecutar_ciclo()
            if not exitoso:
                logging.warning(f"El ciclo falló. Se reintentará en {self.intervalo_reintento_seg / 60} minutos.")
                time.sleep(self.intervalo_reintento_seg)
                logging.info("Ejecutando reintento...")
                exitoso_reintento = self._ejecutar_ciclo()
                if not exitoso_reintento:
                    log_filename = f"logs/error_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
                    with open(log_filename, 'w') as f:
                        f.write(f"Timestamp: {datetime.now()}\n")
                        f.write("El agente no pudo conectarse a Odoo después de dos intentos.\n")
                    logging.error(f"El reintento también falló. Detalles guardados en {log_filename}.")
            logging.info(f"Próximo escaneo programado en {self.intervalo_principal_seg / 60} minutos.")
            time.sleep(self.intervalo_principal_seg)