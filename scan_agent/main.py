# -*- coding: utf-8 -*-
import sys
import logging
from pathlib import Path
from scan.core.recolector import GestorTI

# --- Configuración de Paths e Importaciones ---
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from agent import AgenteScanner
from configurador import load_config, run_configuration_wizard

def iniciar_agente():
    """
    Función principal que carga la configuración y, si es válida,
    inicia el agente de escaneo.
    """
    print("Iniciando Agente de Gestión de Activos...")
    
    force_config = "--config" in sys.argv
    config = load_config()
    
    if force_config or not config:
        config = run_configuration_wizard()
        if not config:
            print("No se pudo obtener una configuración válida. El agente se cerrará.")
            sys.exit(1)

    agente = AgenteScanner(config)
    try:
        agente.iniciar()
    except KeyboardInterrupt:
        print("\nAgente detenido manualmente. ¡Hasta luego!")
    except Exception as e:
        logging.critical(f"Error fatal en el agente: {e}", exc_info=True)

if __name__ == "__main__":
    iniciar_agente()
    #rec = GestorTI()
    #rec.test()