import os
import platform
import subprocess
import json
import socket
import uuid
import psutil
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Configuración inicial
CONFIG_FILE = "sensor_config.json"
REPORT_DIR = "system_reports"
BASE_DIR = Path(__file__).parent

# Para Windows
if os.name == 'nt':
    import wmi
    import winreg

def initialize_config() -> None:
    """Inicializa el archivo de configuración si no existe"""
    default_config = {
        "odoo_url": "http://tuservidor-odoo.com/api/equipos",
        "inventario": {
            "pc": "INV-PC-0000",
            "teclado": "INV-TEC-0000",
            "mouse": "INV-MOU-0000",
            "monitor": "INV-MON-0000",
            "bocinas": "INV-BOC-0000",
            "otros": "SIN-INVENTARIO"
        },
        "ultimo_escaneo": None
    }
    
    if not Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)

def get_config() -> Dict[str, Any]:
    """Obtiene la configuración actual"""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def update_config_last_scan() -> None:
    """Actualiza la fecha del último escaneo"""
    config = get_config()
    config["ultimo_escaneo"] = datetime.now().isoformat()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_os_info() -> Dict[str, str]:
    """Obtiene información básica del sistema operativo"""
    return {
        'sistema': platform.system(),
        'version': platform.version(),
        'arquitectura': platform.machine(),
        'fabricante': platform.node()
    }

def get_hardware_info() -> Dict[str, Any]:
    """Obtiene información de hardware con números de inventario"""
    hardware: Dict[str, Any] = {'dispositivos': []}
    config = get_config()
    
    try:
        if platform.system() == 'Linux':
            lshw = json.loads(subprocess.check_output(['sudo', 'lshw', '-json'], text=True))
            try:
                # Detección mejorada de dispositivos de entrada
                input_devices = subprocess.check_output(['lsinput'], text=True)
                for dev in input_devices.split('\n'):
                    if 'mouse' in dev.lower() or 'touchpad' in dev.lower():
                        parts = dev.split()
                        device_path = parts[0]
                        model = subprocess.check_output(
                            ['udevadm', 'info', '--query=property', '--path', device_path],
                            text=True
                        )
                        model_match = re.search(r'ID_MODEL=(.+)', model)
                        serial_match = re.search(r'ID_SERIAL_SHORT=(.+)', model)
                        
                        hardware['dispositivos'].append({
                            'tipo': 'MOUSE',
                            'modelo': model_match.group(1) if model_match else 'Dispositivo señalador desconocido',
                            'serial': serial_match.group(1) if serial_match else None,
                            'inventario': config['inventario'].get('mouse', config['inventario']['otros'])
                        })
                        
            except Exception as e:
                hardware['error'] = str(e)

            
            peripheral_map = {
                'mouse': ['mouse', 'trackpad'],
                'teclado': ['keyboard'],
                'monitor': ['display', 'vga'],
                'bocinas': ['audio', 'sound']
            }
            
            def process_device(device):
                dev_class = device.get('class', '').lower()
                product = device.get('product', '').lower()
                
                dev_type = 'otros'
                for key, terms in peripheral_map.items():
                    if any(t in dev_class or t in product for t in terms):
                        dev_type = key
                        break
                
                entry = {
                    'tipo': dev_type.upper(),
                    'modelo': device.get('product') or device.get('description'),
                    'serial': device.get('serial'),
                    'inventario': config['inventario'].get(dev_type, config['inventario']['otros'])
                }
                
                if entry['modelo'] and entry['modelo'] not in ['To Be Filled By O.E.M.']:
                    hardware['dispositivos'].append(entry)
                
                for child in device.get('children', []):
                    process_device(child)
            
            process_device(lshw)
            
            # Detección adicional de USB
            try:
                usb_info = subprocess.check_output(['lsusb'], text=True).split('\n')
                for dev in usb_info:
                    if dev:
                        parts = dev.split()
                        model = ' '.join(parts[6:]) if len(parts) > 6 else 'Desconocido'
                        hardware['dispositivos'].append({
                            'tipo': 'USB',
                            'modelo': model,
                            'serial': None,
                            'inventario': config['inventario']['otros']
                        })
            except Exception:
                pass

        elif platform.system() == 'Windows':
            try:
                c = wmi.WMI()

                # Procesador
                for cpu in c.Win32_Processor():
                    hardware['dispositivos'].append({
                        'tipo': 'CPU',
                        'modelo': cpu.Name,
                        'serial': cpu.ProcessorId.strip() if cpu.ProcessorId else None,
                        'inventario': config['inventario'].get('cpu', config['inventario']['otros'])
                    })

                # Discos duros
                for disk in c.Win32_DiskDrive():
                    serial = disk.SerialNumber.strip() if disk.SerialNumber else None
                    if serial and len(serial) == 40:  # Algunos seriales vienen con prefijos
                        serial = serial[-20:]  # Tomar los últimos 20 caracteres
                    hardware['dispositivos'].append({
                        'tipo': 'DISCO',
                        'modelo': disk.Model,
                        'serial': serial,
                        'inventario': config['inventario'].get('disco', config['inventario']['otros'])
                    })

                # Memoria RAM
                for mem in c.Win32_PhysicalMemory():
                    hardware['dispositivos'].append({
                        'tipo': 'RAM',
                        'modelo': f"{mem.Manufacturer} {mem.PartNumber}",
                        'serial': mem.SerialNumber.strip(),
                    })

                # Tarjetas de red físicas
                for nic in c.Win32_NetworkAdapter(PhysicalAdapter=True):
                    if nic.MACAddress:
                        hardware['dispositivos'].append({
                            'tipo': 'RED',
                            'modelo': nic.Name,
                            'serial': nic.MACAddress,
                        })

                # Dispositivos USB
                for usb in c.Win32_PnPEntity(ConfigManagerErrorCode=0):
                    if 'USB' in usb.DeviceID:
                        hardware['dispositivos'].append({
                            'tipo': 'USB',
                            'modelo': usb.Name.split('(')[0].strip(),
                            'serial': usb.DeviceID.split('\\')[-1],
                            'inventario': config['inventario'].get('usb', config['inventario']['otros'])
                        })

                # Tarjeta gráfica
                for gpu in c.Win32_VideoController():
                    hardware['dispositivos'].append({
                        'tipo': 'GPU',
                        'modelo': gpu.Name,
                        'serial': None,
                        'inventario': config['inventario'].get('gpu', config['inventario']['otros'])
                    })
                 # Detección específica de dispositivos señaladores
                pointing_devices = c.Win32_PointingDevice()
                for mouse in pointing_devices:
                    hardware['dispositivos'].append({
                        'tipo': 'MOUSE',
                        'modelo': mouse.Name.split('(')[0].strip(),
                        'serial': mouse.DeviceID.split('\\')[-1],
                        'inventario': config['inventario'].get('mouse', config['inventario']['otros'])
                    })
                
                # Detección alternativa por interfaz HID
                hid_devices = c.Win32_PnPEntity(ConfigManagerErrorCode=0)
                for dev in hid_devices:
                    if 'HID' in dev.DeviceID and 'VID' in dev.DeviceID:
                        device_info = subprocess.check_output(
                            ['powershell', f'Get-PnpDevice -InstanceId "{dev.DeviceID}" | Select-Object -Property FriendlyName'],
                            text=True
                        ).strip()
                        if 'mouse' in device_info.lower():
                            hardware['dispositivos'].append({
                                'tipo': 'MOUSE',
                                'modelo': dev.Name,
                                'serial': dev.DeviceID.split('\\')[-1],
                                'inventario': config['inventario'].get('mouse', config['inventario']['otros'])
                            })

                    
            except Exception as e:
                hardware['error'] = f"Error WMI: {str(e)}. Ejecutar como Administrador y verificar WMI."

    except Exception as e:
        hardware['error'] = str(e)
    
    # Filtrado de dispositivos inválidos
    valid_devices = []
    for d in hardware['dispositivos']:
        if d['modelo'] and d['modelo'] not in ['To Be Filled By O.E.M.']:
            # Normalizar modelo
            d['modelo'] = d['modelo'].replace('\r','').replace('\n','').strip()
            valid_devices.append(d)
    
    hardware['dispositivos'] = valid_devices
    
    return hardware

def get_installed_software() -> Dict[str, Any]:
    """Obtiene lista de software instalado"""
    software: Dict[str, Any] = {}
    
    try:
        if platform.system() == 'Linux':
            dpkg = subprocess.check_output(['dpkg', '--get-selections'], text=True)
            software['paquetes'] = [p.split('\t')[0] for p in dpkg.split('\n') if p and not p.startswith('deinstall')]
            
        elif platform.system() == 'Windows':
            software['programas'] = []
            reg_paths = [
                r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
                r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
            ]
            
            for reg_path in reg_paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                    for i in range(0, winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                            name = winreg.QueryValueEx(subkey, 'DisplayName')[0]
                            software['programas'].append(name)
                        except (OSError, FileNotFoundError):
                            continue
                except FileNotFoundError:
                    continue
            
            software['programas'] = list(filter(None, list(set(software['programas']))))

    except Exception as e:
        software['error'] = str(e)
    
    return software

def get_network_info() -> Dict[str, Any]:
    """Obtiene información básica de red"""
    network: Dict[str, Any] = {}
    
    try:
        network['hostname'] = socket.gethostname()
        network['mac'] = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
        
        # Interfaces de red
        network['interfaces'] = []
        for name, addrs in psutil.net_if_addrs().items():
            interface_info = {'nombre': name, 'ipv4': [], 'mac': None}
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interface_info['ipv4'].append(addr.address)
                elif addr.family == socket.AF_PACKET:
                    interface_info['mac'] = addr.address
            network['interfaces'].append(interface_info)
            
    except Exception as e:
        network['error'] = str(e)
    
    return network

def generate_report() -> str:
    """Genera el reporte completo del sistema"""
    report = {
        'metadata': {
            'fecha_escaneo': datetime.now().isoformat(),
            'inventario_pc': get_config()['inventario']['pc']
        },
        'sistema': get_os_info(),
        'hardware': get_hardware_info(),
        'software': get_installed_software(),
        'red': get_network_info()
    }
    
    # Crear directorio de reportes
    report_dir = BASE_DIR / REPORT_DIR
    report_dir.mkdir(exist_ok=True)
    
    # Nombre de archivo único
    report_file = report_dir / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    return str(report_file)

import json
import xmlrpc.client
import traceback
def send_to_odoo() -> bool:
    """Envía el reporte a un modelo personalizado en Odoo vía XML-RPC."""
    try:
        # 1) Cargamos configuración
        config = get_config()
        url = 'https://testing.asisurl.cu'                # ej: "https://mi-odoo.com"
        db = 'suite'               # ej: "mi_basedatos"
        username = 'admin'           # ej: "admin"
        password = 'admin'          # ej: "secret"

        # 2) Conexión al API de autenticación
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate(db, username, password, {})

        if not uid:
            print("Error: credenciales inválidas")
            return False

        # 3) Conexión al API de objetos
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

        # 4) Leemos el reporte JSON

        #################################software##################################################
        software = get_installed_software()
    
         # Dependiendo de la plataforma, la clave será 'paquetes' o 'programas'
        lista = software.get('programas') or software.get('paquetes') or []
    
        for item in lista:
            # aquí 'item' es el nombre de cada programa/paquete instalado
            print(f"- {item}")
        
        ######################################################################################
        # 5) Preparamos los datos a enviar
        #dispositivos = report['hardware']['dispositivos']
            vals = {
                'name': f"{item}",          # campo de texto
                'inv': "1234",                # campo integer
                'type': 'software',  
                # suponiendo que tus programas son registros Many2many en Odoo
                'status': 'active',
                'description': " ",
                'version':"1"
            }

            # 6) Ejecutamos el create
            # new_id = models.execute_kw(
            #     db, uid, password,
            #     'it.asset.software',   # nombre técnico de tu modelo
            #     'create', 
            #     [vals]
            # )

            #print(f"✅ Registro creado en Odoo con ID: {new_id}")
        ############################hardware####################################################
        hardware_1 = get_hardware_info()
        interface_1 = get_network_info()
         # Dependiendo de la plataforma, la clave será 'paquetes' o 'programas'
        dispositivos = hardware_1.get('dispositivos')  or []
        interface = interface_1.get('interfaces')  or []
        hardware = {
                'name': config['inventario'].get('pc', config['inventario']['otros']),          # campo de texto
                'inv': "1234",                # campo integer
                'type': 'hardware',  
                'status': 'active',
                'description': "te lo debo ",
                'components_ids': [(6, 0, [p['id'] for p in dispositivos if 'id' in p])],  
            }

        new_id = models.execute_kw(
                db, uid, password,
                'it.asset.hardware',   # nombre técnico de tu modelo
                'create', 
                [hardware]
            )
            ########################################################################################
        return True

    except Exception as e:
        traceback.print_exc()
        return False


def main():
    initialize_config()
    
    print("\n" + "="*40)
    print("  Sistema de Monitoreo de Hardware")
    print("="*40)
    
    # Paso 1: Escaneo completo
    print("\n▶ Iniciando escaneo del sistema...")
    report_file = generate_report()
    
    # Paso 2: Actualizar configuración
    update_config_last_scan()
    
    # Paso 3: Envío simulado
    print("\n▶ Procesando resultados...")
    if send_to_odoo(report_file):
        print("\n✔ Escaneo completado exitosamente")
    else:
        print("\n✖ Error en el proceso de envío")
    
    print(f"\n● Reporte generado en: {report_file}")

if __name__ == '__main__':
    initialize_config()
    
    #main()
    send_to_odoo()