# -*- coding: utf-8 -*-
import json
import os
import sys
import platform
import subprocess
from pathlib import Path

# Importación segura para la GUI
try:
    from configurador_gui import ConfiguratorApp
except ImportError:
    ConfiguratorApp = None

CONFIG_FILE = Path(__file__).parent / 'config_agente.json'

def load_config():
    """Carga la configuración desde el archivo JSON."""
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error al leer el archivo de configuración: {e}")
        return None

def save_config(config_data):
    """Guarda la configuración en el archivo JSON."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error al guardar el archivo de configuración: {e}")
        return False

def run_configuration_wizard():
    """Ejecuta el asistente de configuración GUI."""
    if not ConfiguratorApp:
        print("Error: Tkinter no está disponible. No se puede mostrar la GUI de configuración.")
        return None

    print("Iniciando asistente de configuración...")
    current_config = load_config()
    app = ConfiguratorApp(initial_config=current_config)
    app.mainloop()

    if app.saved:
        if save_config(app.config_data):
            print("Configuración guardada exitosamente.")
            setup_persistence()
            return app.config_data
    else:
        print("Configuración cancelada por el usuario.")
    return None

def setup_persistence():
    """Configura el script para que se inicie automáticamente con el sistema."""
    os_type = platform.system()
    print(f"Detectado sistema operativo: {os_type}. Intentando configurar persistencia...")

    # Obtenemos la ruta absoluta al ejecutable de Python y al script principal
    python_executable = sys.executable
    script_path = str(Path(__file__).parent / 'main.py')

    try:
        if os_type == "Windows":
            _setup_windows_persistence(python_executable, script_path)
        elif os_type == "Linux":
            _setup_linux_persistence(python_executable, script_path)
        elif os_type == "Darwin": # macOS
            _setup_macos_persistence(python_executable, script_path)
        else:
            print(f"La configuración de persistencia automática no es compatible con {os_type}.")
    except Exception as e:
        print(f"Error al configurar la persistencia: {e}")

def _setup_windows_persistence(python_exe, script_path):
    """Crea una entrada en el registro de Windows para el inicio automático."""
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    key_name = "ScanAgentSGICH"
    command = f'"{python_exe}" "{script_path}"'
    
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, command)
    print("Persistencia configurada para Windows.")

def _setup_linux_persistence(python_exe, script_path):
    """Crea un archivo .desktop en la carpeta de autostart de Linux."""
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = autostart_dir / "scan_agent.desktop"
    
    desktop_content = f"""[Desktop Entry]
Type=Application
Exec="{python_exe}" "{script_path}"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name[en_US]=Scan Agent
Name=Scan Agent
Comment[en_US]=Starts the IT asset scanning agent
Comment=Inicia el agente de escaneo de activos de TI
"""
    with open(desktop_file, "w", encoding="utf-8") as f:
        f.write(desktop_content)
    print("Persistencia configurada para Linux.")

def _setup_macos_persistence(python_exe, script_path):
    """Crea un archivo .plist en la carpeta LaunchAgents de macOS."""
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_file = launch_agents_dir / "com.sgich.scanagent.plist"
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sgich.scanagent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    with open(plist_file, "w", encoding="utf-8") as f:
        f.write(plist_content)
    print("Persistencia configurada para macOS. Es posible que necesites reiniciar para que tenga efecto.")
