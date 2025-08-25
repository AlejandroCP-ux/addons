import platform
import subprocess
import re
import json

class RecolectorGPU:
    def obtener_info(self):
        so = platform.system()
        if so == "Windows":
            return self._obtener_info_windows()
        elif so == "Linux":
            return self._obtener_info_linux()
        else:
            return self._info_basica()
    
    def _info_basica(self):
        """Información básica cuando no se puede obtener datos específicos"""
        return [{
            "Tipo": "Desconocido",
            "Fabricante": "Desconocido",
            "Modelo": "Desconocido",
            "Memoria (MB)": 0,
            "Driver versión": "Desconocido"
        }]
    
    def _obtener_info_windows(self):
        """Obtiene información de GPU en Windows usando WMI"""
        try:
            import wmi
            c = wmi.WMI()
            gpus = []
            
            # Obtener adaptadores de video
            for gpu in c.Win32_VideoController():
                # Filtrar dispositivos básicos de visualización
                if "Microsoft Basic Display" in gpu.Name:
                    continue
                    
                gpus.append({
                    "ID único": self._generar_id_unico(gpu),
                    "Fabricante": self._determinar_fabricante(gpu.Name),
                    "Modelo": gpu.Name,
                    "Tipo": "Dedicada" if "Intel" not in gpu.Name else "Integrada",
                    "Memoria (MB)": int(gpu.AdapterRAM) // (1024 * 1024) if gpu.AdapterRAM else 0,
                    "Driver versión": gpu.DriverVersion,
                    "Resolución actual": f"{gpu.CurrentHorizontalResolution}x{gpu.CurrentVerticalResolution}",
                    "PNP Device ID": gpu.PNPDeviceID
                })
            
            return gpus
        except Exception as e:
            return self._info_basica()
    
    def _obtener_info_linux(self):
        """Obtiene información de GPU en Linux usando lspci y otras herramientas"""
        try:
            gpus = []
            
            # Obtener GPUs usando lspci
            output = subprocess.check_output(
                "lspci -vmm -k -D | grep -E '^(Vendor|Device|SVendor|SDevice|Driver|Module|Class):' -A 1",
                shell=True,
                text=True
            )
            
            # Procesar bloques de dispositivos
            bloques = re.split(r'\n--\n', output)
            for bloque in bloques:
                if "Class: 03" not in bloque:  # Filtrar solo dispositivos VGA
                    continue
                    
                info = {}
                lineas = bloque.split('\n')
                for linea in lineas:
                    if ': ' in linea:
                        key, value = linea.split(': ', 1)
                        info[key.strip()] = value.strip()
                
                # Determinar fabricante y modelo
                fabricante = info.get("SVendor", info.get("Vendor", "Desconocido"))
                modelo = info.get("SDevice", info.get("Device", "Desconocido"))
                
                # Obtener memoria
                memoria = self._obtener_memoria_gpu_linux(info.get("Slot", ""))
                
                # Obtener driver
                driver = info.get("Driver", info.get("Module", "Desconocido"))
                
                # Obtener resolución actual
                resolucion = self._obtener_resolucion_linux()
                
                gpus.append({
                    "ID único": self._generar_id_unico_linux(info),
                    "Fabricante": fabricante,
                    "Modelo": modelo,
                    "Tipo": self._determinar_tipo_gpu(fabricante, modelo),
                    "Memoria (MB)": memoria,
                    "Driver versión": driver,
                    "Resolución actual": resolucion,
                    "PCI ID": info.get("Slot", "")
                })
            
            return gpus
        except Exception as e:
            return self._info_basica()
    
    def _generar_id_unico(self, gpu):
        """Genera ID único para GPU en Windows"""
        atributos = f"{gpu.PNPDeviceID}-{gpu.Name}"
        import hashlib
        return hashlib.sha256(atributos.encode()).hexdigest()[:16].upper()
    
    def _generar_id_unico_linux(self, info):
        """Genera ID único para GPU en Linux"""
        atributos = f"{info.get('Slot','')}-{info.get('SDevice','')}-{info.get('SVendor','')}"
        import hashlib
        return hashlib.sha256(atributos.encode()).hexdigest()[:16].upper()
    
    def _determinar_fabricante(self, nombre):
        """Determina el fabricante basado en el nombre del dispositivo"""
        fabricantes = ["NVIDIA", "AMD", "ATI", "Intel", "ASUS", "MSI", "Gigabyte"]
        for fab in fabricantes:
            if fab.lower() in nombre.lower():
                return fab
        return "Desconocido"
    
    def _determinar_tipo_gpu(self, fabricante, modelo):
        """Determina si la GPU es integrada o dedicada"""
        if "Intel" in fabricante:
            return "Integrada"
        if "AMD" in fabricante and "Radeon" in modelo:
            return "Dedicada"
        if "NVIDIA" in fabricante:
            return "Dedicada"
        return "Desconocido"
    
    def _obtener_memoria_gpu_linux(self, pci_id):
        """Obtiene la memoria de la GPU en Linux"""
        try:
            if not pci_id:
                return 0
                
            # Obtener información detallada de la GPU
            output = subprocess.check_output(
                f"lspci -v -s {pci_id}",
                shell=True,
                text=True
            )
            
            # Buscar información de memoria
            for linea in output.splitlines():
                if "prefetchable" in linea and "size=" in linea:
                    match = re.search(r'size=(\d+)(\w+)', linea)
                    if match:
                        valor, unidad = match.groups()
                        multiplicador = {'M': 1, 'G': 1024}.get(unidad, 1)
                        return int(valor) * multiplicador
            return 0
        except:
            return 0
    
    def _obtener_resolucion_linux(self):
        """Obtiene la resolución actual en Linux"""
        try:
            output = subprocess.check_output(
                "xrandr --current",
                shell=True,
                text=True
            )
            
            for linea in output.splitlines():
                if "*" in linea:
                    match = re.search(r'(\d+x\d+)', linea)
                    if match:
                        return match.group(1)
            return "Desconocido"
        except:
            return "Desconocido"