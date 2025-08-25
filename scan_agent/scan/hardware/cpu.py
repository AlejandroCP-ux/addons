import platform
import psutil
import subprocess
import re

class RecolectorCPU:
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
        return {
            "Fabricante": "Desconocido",
            "Modelo": platform.processor(),
            "Núcleos físicos": psutil.cpu_count(logical=False),
            "Núcleos totales": psutil.cpu_count(logical=True),
            "Frecuencia máxima (MHz)": psutil.cpu_freq().max,
            "Arquitectura": platform.architecture()[0]
        }
    
    def _obtener_info_windows(self):
        """Obtiene información detallada del CPU en Windows usando WMI"""
        try:
            import wmi
            c = wmi.WMI()
            cpu = c.Win32_Processor()[0]  # Tomamos el primer procesador
            
            return {
                "Fabricante": cpu.Manufacturer,
                "Modelo": cpu.Name,
                "ID del producto": cpu.ProcessorId.strip(),
                "ID único": self._generar_id_unico(cpu),
                "Núcleos físicos": cpu.NumberOfCores,
                "Núcleos totales": cpu.NumberOfLogicalProcessors,
                "Frecuencia base (MHz)": cpu.MaxClockSpeed,
                "Frecuencia actual (MHz)": psutil.cpu_freq().current,
                "Socket": cpu.SocketDesignation,
                "Versión de stepping": cpu.Stepping,
                "Familia": cpu.Family,
                "Arquitectura": platform.architecture()[0],
                "Caché L2 (KB)": cpu.L2CacheSize,
                "Caché L3 (KB)": cpu.L3CacheSize
            }
        except Exception as e:
            # Fallback a información básica si hay error
            return self._info_basica()
    
    def _obtener_info_linux(self):
        """Obtiene información detallada del CPU en Linux usando /proc/cpuinfo"""
        try:
            info_cpu = {}
            with open('/proc/cpuinfo', 'r') as f:
                data = f.read()
            
            # Extraemos información del primer núcleo (suficiente para datos generales)
            for line in data.split('\n'):
                if line.strip() == '':  # Separador entre procesadores
                    break
                if ':' in line:
                    key, value = [part.strip() for part in line.split(':', 1)]
                    info_cpu[key] = value
            
            # Convertimos a estructura consistente
            return {
                "Fabricante": info_cpu.get('vendor_id', 'Desconocido'),
                "Modelo": info_cpu.get('model name', info_cpu.get('Processor', 'Desconocido')),
                "ID del producto": info_cpu.get('cpu family', '') + "-" + info_cpu.get('model', ''),
                "ID único": self._generar_id_unico(info_cpu),
                "Núcleos físicos": psutil.cpu_count(logical=False),
                "Núcleos totales": psutil.cpu_count(logical=True),
                "Frecuencia base (MHz)": info_cpu.get('cpu MHz', 'Desconocido'),
                "Frecuencia máxima (MHz)": self._obtener_frecuencia_max_linux(),
                "Socket": self._obtener_socket_linux(),
                "Versión de stepping": info_cpu.get('stepping', 'Desconocido'),
                "Familia": info_cpu.get('cpu family', 'Desconocido'),
                "Arquitectura": platform.architecture()[0],
                "Caché L2 (KB)": self._obtener_cache_linux('L2'),
                "Caché L3 (KB)": self._obtener_cache_linux('L3')
            }
        except Exception as e:
            return self._info_basica()
    
    def _generar_id_unico(self, datos):
        """
        Genera un ID único basado en atributos invariables del CPU.
        Este ID será consistente incluso entre reinstalaciones del sistema.
        """
        if isinstance(datos, dict):  # Linux
            atributos = f"{datos.get('vendor_id','')}-{datos.get('cpu family','')}-" \
                       f"{datos.get('model','')}-{datos.get('stepping','')}-" \
                       f"{datos.get('model name','')}"
        else:  # Windows WMI object
            atributos = f"{datos.Manufacturer}-{datos.Family}-{datos.Stepping}-" \
                       f"{datos.ProcessorId}"
        
        # Generamos un hash SHA-256 de los atributos
        import hashlib
        return hashlib.sha256(atributos.encode()).hexdigest()[:16].upper()
    
    def _obtener_frecuencia_max_linux(self):
        """Obtiene la frecuencia máxima del CPU en Linux"""
        try:
            output = subprocess.check_output("lscpu", shell=True, text=True)
            for line in output.splitlines():
                if "CPU max MHz" in line:
                    return line.split(":")[1].strip()
        except:
            return "Desconocido"
    
    def _obtener_socket_linux(self):
        """Obtiene información del socket en Linux"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                data = f.read()
                if "physical id" in data:
                    physical_ids = re.findall(r'physical id\s*:\s*(\d+)', data)
                    return f"Socket {max(map(int, physical_ids)) + 1}"
        except:
            pass
        return "Desconocido"
    
    def _obtener_cache_linux(self, nivel):
        """Obtiene tamaño de caché específico en Linux"""
        try:
            output = subprocess.check_output(f"lscpu", shell=True, text=True)
            for line in output.splitlines():
                if f"{nivel} cache" in line:
                    size = line.split(":")[1].strip()
                    # Convertir a KB si está en MB
                    if "MiB" in size:
                        return f"{float(size.replace(' MiB', '')) * 1024:.0f}"
                    elif "KiB" in size:
                        return size.replace(" KiB", "")
            return "Desconocido"
        except:
            return "Desconocido"