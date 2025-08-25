import platform
import sys
import subprocess
import re

def get_ram_info_windows():
    """Obtiene información de RAM en sistemas Windows usando WMI"""
    try:
        import wmi
    except ImportError:
        print("Instalando dependencia para Windows...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "wmi"])
        import wmi

    w = wmi.WMI()
    ram_modules = []
    for module in w.Win32_PhysicalMemory():
        ram_info = {
            'Fabricante': module.Manufacturer,
            'Modelo': module.PartNumber.strip(),
            'Tamaño (GB)': round(int(module.Capacity) / (1024**3), 2),
            'Número de Serie': module.SerialNumber.strip(),
            'Tipo': module.MemoryType,
            'Velocidad (MHz)': module.Speed,
            'Factor de Forma': module.FormFactor,
            'Banco': module.BankLabel,
            'Slot': module.DeviceLocator
        }
        ram_modules.append(ram_info)
    return ram_modules

def get_ram_info_linux():
    """Obtiene información de RAM en sistemas Linux usando dmidecode"""
    try:
        result = subprocess.run(
            ['sudo', 'dmidecode', '-t', 'memory'],
            capture_output=True,
            text=True,
            check=True
        )
        return parse_dmidecode_output(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error: {e}\nSe requiere sudo y dmidecode instalado")
        print("Instala dmidecode con: sudo apt-get install dmidecode")
        return []

def parse_dmidecode_output(output):
    """Parsea la salida de dmidecode para extraer información de RAM"""
    modules = []
    current_module = {}
    in_memory_device = False
    
    for line in output.splitlines():
        if line.startswith('Memory Device'):
            if current_module:
                modules.append(current_module)
                current_module = {}
            in_memory_device = True
            continue
        
        if in_memory_device and ':' in line:
            key, value = [part.strip() for part in line.split(':', 1)]
            value = value.strip()
            
            if key == 'Size':
                if 'MB' in value:
                    size_gb = round(float(re.search(r'(\d+)', value).group(1)) / 1024, 2)
                elif 'GB' in value:
                    size_gb = float(re.search(r'(\d+)', value).group(1))
                else:
                    size_gb = 0
                current_module['Tamaño (GB)'] = size_gb
            
            elif key == 'Type':
                current_module['Tipo'] = value.split()[0] if value != 'Unknown' else 'Desconocido'
            
            elif key == 'Manufacturer':
                current_module['Fabricante'] = value if value != 'Unknown' else 'Desconocido'
            
            elif key == 'Serial Number':
                current_module['Número de Serie'] = value if value != 'Unknown' else 'Desconocido'
            
            elif key == 'Part Number':
                current_module['Modelo'] = value.strip()
            
            elif key == 'Speed':
                if 'MHz' in value:
                    current_module['Velocidad (MHz)'] = int(re.search(r'(\d+)', value).group(1))
    
    if current_module:
        modules.append(current_module)
    
    # Filtrar módulos vacíos (slots sin RAM)
    return [m for m in modules if m.get('Tamaño (GB)', 0) > 0]

def print_ram_info(modules):
    """Muestra la información de los módulos RAM de forma legible"""
    if not modules:
        print("No se encontraron módulos de RAM")
        return
    
    print("\nDetalles de los módulos RAM instalados:")
    print("-" * 70)
    for i, module in enumerate(modules, 1):
        print(f"Módulo #{i}:")
        for key, value in module.items():
            print(f"  {key}: {value}")
        print("-" * 70)

def main():
    system = platform.system()
    print(f"Sistema detectado: {system}")
    
    if system == 'Windows':
        ram_modules = get_ram_info_windows()
    elif system == 'Linux':
        ram_modules = get_ram_info_linux()
    else:
        print("Sistema operativo no compatible")
        return
    
    print_ram_info(ram_modules)


if __name__ == "__main__":
    main()