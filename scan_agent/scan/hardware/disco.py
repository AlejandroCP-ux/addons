import platform
import subprocess
import re
import psutil
import json

class RecolectorDiscos:
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
        discos = []
        for particion in psutil.disk_partitions():
            if not self._es_extraible(particion.device):
                uso = psutil.disk_usage(particion.mountpoint)
                discos.append({
                    "Punto de montaje": particion.mountpoint,
                    "Dispositivo": particion.device,
                    "Sistema archivos": particion.fstype,
                    "Tamaño total (GB)": round(uso.total / (1024**3), 2),
                    "Espacio usado (GB)": round(uso.used / (1024**3), 2),
                    "Tipo": "Desconocido"
                })
        return discos
    
    def _es_extraible(self, dispositivo):
        """Filtra dispositivos extraíbles basándose en patrones comunes"""
        patrones_extraibles = [
            r'/media/',
            r'/mnt/removable',
            r'/dev/sd[a-z][1-9]?$',
            r'/dev/mmcblk[0-9]p[0-9]?$',
            r'[A-Z]:\\Removable',
            r'USB',
            r'Removable'
        ]
        return any(re.search(p, dispositivo, re.IGNORECASE) for p in patrones_extraibles)
    
    def _obtener_info_windows(self):
        """Obtiene información detallada de discos en Windows usando WMI"""
        try:
            import wmi
            c = wmi.WMI()
            discos = []
            
            # Obtener discos físicos
            for fisico in c.Win32_DiskDrive():
                if fisico.InterfaceType == "USB":
                    continue
                
                # Obtener particiones asociadas
                particiones = []
                for particion in c.Win32_DiskPartition(DeviceID=fisico.DeviceID):
                    for logico in c.Win32_LogicalDisk(DeviceID=particion.DeviceID):
                        uso = psutil.disk_usage(logico.DeviceID)
                        particiones.append({
                            "Letra": logico.DeviceID,
                            "Tamaño (GB)": round(int(logico.Size) / (1024**3), 2) if logico.Size else 0,
                            "Espacio libre (GB)": round(int(logico.FreeSpace) / (1024**3), 2) if logico.FreeSpace else 0,
                            "Sistema archivos": logico.FileSystem,
                            "Tamaño real (GB)": round(uso.total / (1024**3), 2)
                        })
                
                discos.append({
                    "ID único": self._generar_id_unico(fisico),
                    "Modelo": fisico.Model,
                    "Fabricante": fisico.Manufacturer,
                    "Número serie": fisico.SerialNumber.strip() if fisico.SerialNumber else "Desconocido",
                    "Tamaño (GB)": round(int(fisico.Size) / (1024**3), 2),
                    "Tipo interfaz": fisico.InterfaceType,
                    "Tipo medio": self._determinar_tipo_medio(fisico.MediaType, fisico.Model),
                    "Particiones": particiones,
                    "Tipo": "SSD" if "SSD" in fisico.MediaType else "HDD"
                })
            
            return discos
        except Exception as e:
            return self._info_basica()
    
    def _obtener_info_linux(self):
        """Obtiene información detallada de discos en Linux usando comandos del sistema"""
        try:
            discos = []
            # Obtener lista de discos con lsblk
            lsblk = subprocess.check_output(
                "lsblk -J -o NAME,MODEL,SERIAL,SIZE,ROTA,MOUNTPOINT,FSTYPE,TYPE,TRAN",
                shell=True,
                text=True
            )
            datos = json.loads(lsblk)
            
            for dispositivo in datos["blockdevices"]:
                if dispositivo['type'] == 'disk' and not self._es_extraible(dispositivo['name']):
                    # Obtener detalles adicionales
                    rotacional = dispositivo.get('rota', '1') == '1'
                    tipo_interfaz = dispositivo.get('tran', 'Desconocido')
                    
                    # Obtener particiones
                    particiones = []
                    for part in dispositivo.get('children', []):
                        if part['type'] == 'part':
                            uso = psutil.disk_usage(part['mountpoint']) if part.get('mountpoint') else None
                            particiones.append({
                                "Punto montaje": part.get('mountpoint', ''),
                                "Sistema archivos": part.get('fstype', ''),
                                "Tamaño": part['size'],
                                "Tamaño real (GB)": round(uso.total / (1024**3), 2) if uso else 0
                            })
                    
                    discos.append({
                        "ID único": self._generar_id_unico_linux(dispositivo),
                        "Modelo": dispositivo.get('model', 'Desconocido'),
                        "Fabricante": self._obtener_fabricante(dispositivo.get('model', '')),
                        "Número serie": dispositivo.get('serial', 'Desconocido'),
                        "Tamaño (GB)": self._convertir_tamano(dispositivo['size']),
                        "Tipo interfaz": tipo_interfaz,
                        "Tipo medio": "HDD" if rotacional else "SSD",
                        "Particiones": particiones,
                        "Tipo": "SSD" if not rotacional else "HDD"
                    })
            
            return discos
        except Exception as e:
            return self._info_basica()
    
    def _generar_id_unico(self, disco):
        """Genera ID único para discos en Windows"""
        atributos = f"{disco.Model}-{disco.SerialNumber}-{disco.InterfaceType}"
        import hashlib
        return hashlib.sha256(atributos.encode()).hexdigest()[:16].upper()
    
    def _generar_id_unico_linux(self, disco):
        """Genera ID único para discos en Linux"""
        atributos = f"{disco.get('model','')}-{disco.get('serial','')}-{disco.get('tran','')}"
        import hashlib
        return hashlib.sha256(atributos.encode()).hexdigest()[:16].upper()
    
    def _determinar_tipo_medio(self, media_type, modelo):
        """Determina el tipo de medio basado en información de Windows"""
        if "SSD" in media_type or "SSD" in modelo:
            return "SSD"
        if "HDD" in media_type or "Hard Disk" in media_type:
            return "HDD"
        if "NVMe" in modelo:
            return "NVMe SSD"
        return "Desconocido"
    
    def _obtener_fabricante(self, modelo):
        """Extrae el fabricante del modelo del disco"""
        fabricantes = ["Samsung", "Seagate", "Western Digital", "Toshiba", "Kingston", "Crucial", "Intel"]
        for fab in fabricantes:
            if fab.lower() in modelo.lower():
                return fab
        return "Desconocido"
    
    def _convertir_tamano(self, tamano_str):
        """Convierte tamaños de cadena a GB numéricos"""
        unidades = {"T": 1024, "G": 1, "M": 1/1024, "K": 1/(1024**2)}
        match = re.match(r"(\d+\.?\d*)([TGMK])", tamano_str)
        if match:
            valor, unidad = match.groups()
            return round(float(valor) * unidades.get(unidad, 1), 2)
        return 0