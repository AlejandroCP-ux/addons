import platform
import subprocess
import re
try:
    import winreg
except:
    print("[Error][PROGRAMAS] import winreg")
import os
import glob
from datetime import datetime

class RecolectorProgramas:
    def obtener_info(self):
        """Obtiene información de programas instalados en el sistema"""
        print("[DEBUG][PROGRAMAS] Iniciando recolección de información del sistema...")
        so = platform.system()
        print(f"[DEBUG][PROGRAMAS] Sistema operativo detectado: {so}")
        
        if so == "Windows":
            return self._obtener_programas_windows()
        elif so == "Linux":
            return self._obtener_programas_linux()
        else:
            print(f"[DEBUG][PROGRAMAS] Sistema operativo no soportado: {so}")
            return self._obtener_programas_generico()
    
    def _obtener_programas_windows(self):
        """Obtiene programas instalados en Windows usando el registro"""
        print("[DEBUG][PROGRAMAS] Iniciando búsqueda de programas en Windows...")
        
        # Primero verificamos si estamos en Windows
        if platform.system() != "Windows":
            print("[ERROR][PROGRAMAS] Intentando ejecutar código Windows en un sistema no Windows")
            return []
        
        # Importamos winreg al inicio del método
        try:
            import winreg
        except ImportError:
            print("[ERROR][PROGRAMAS] No se pudo importar winreg. ¿Tienes permisos de administrador?")
            return []
        
        programas = []
        rutas_registro = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
        
        for ruta in rutas_registro:
            print(f"[DEBUG][PROGRAMAS] Buscando en ruta del registro: {ruta}")
            try:
                # Abrimos la clave del registro
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta) as key:
                    idx = 0
                    while True:
                        try:
                            # Obtenemos el nombre de la subclave
                            subkey_name = winreg.EnumKey(key, idx)
                            subkey_path = f"{ruta}\\{subkey_name}"
                            
                            # Abrimos la subclave
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as subkey:
                                programa = {}
                                try:
                                    # Obtenemos la información del programa
                                    programa["nombre"] = self._obtener_valor_registro(subkey, "DisplayName")
                                    programa["version"] = self._obtener_valor_registro(subkey, "DisplayVersion")
                                    programa["fabricante"] = self._obtener_valor_registro(subkey, "Publisher")
                                    
                                    programa["licencia"] = self._obtener_clave_licencia(subkey)
                                    
                                    programa["fecha_instalacion"] = self._obtener_valor_registro(subkey, "InstallDate")
                                    programa["tamaño"] = self._convertir_tamano(self._obtener_valor_registro(subkey, "EstimatedSize"))
                                    programa["ubicacion"] = self._obtener_valor_registro(subkey, "InstallLocation")
                                    
                                    # Filtramos programas del sistema
                                    if programa["nombre"] and not programa["nombre"].startswith("KB") and not programa["nombre"].startswith("Update for"):
                                        programas.append(programa)
                                        print(f"[DEBUG][PROGRAMAS] Programa encontrado: {programa['nombre']}")
                                
                                except OSError as e:
                                    print(f"[ERROR][PROGRAMAS] Error al procesar programa: {str(e)}")
                        except OSError:
                            break
                        idx += 1
            except Exception as e:
                print(f"[ERROR][PROGRAMAS] Error al acceder a la ruta del registro {ruta}: {str(e)}")
        
        print(f"[DEBUG][PROGRAMAS] Total de programas encontrados en Windows: {len(programas)}")
        return programas

    def _obtener_programas_linux(self):
        """Obtiene programas instalados en Linux usando diferentes métodos"""
        print("[DEBUG][PROGRAMAS] Iniciando búsqueda de programas en Linux...")
        try:
            programas = []
            
            # Método 1: Paquetes .deb (Debian/Ubuntu)
            if os.path.exists("/var/lib/dpkg/status"):
                print("[DEBUG][PROGRAMAS] Detectado sistema Debian/Ubuntu")
                programas.extend(self._obtener_paquetes_deb())
            
            # Método 2: Paquetes .rpm (RedHat/Fedora)
            elif os.path.exists("/var/lib/rpm"):
                print("[DEBUG][PROGRAMAS] Detectado sistema RedHat/Fedora")
                programas.extend(self._obtener_paquetes_rpm())
            
            # Método 3: Snap packages
            programas.extend(self._obtener_paquetes_snap())
            
            # Método 4: Flatpak packages
            programas.extend(self._obtener_paquetes_flatpak())
            
            print(f"[DEBUG][PROGRAMAS] Total de programas encontrados en Linux: {len(programas)}")
            return programas
        except Exception as e:
            print(f"[ERROR][PROGRAMAS] Error al obtener programas Linux: {str(e)}")
            return []

    def _obtener_valor_registro(self, key, value_name):
        """Obtiene un valor del registro de Windows"""
        print(f"[DEBUG][PROGRAMAS] Leyendo valor del registro: {value_name}")
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            print(f"[DEBUG][PROGRAMAS] Valor obtenido: {value}")
            return value
        except OSError as e:
            print(f"[ERROR][PROGRAMAS] Error al leer valor del registro: {str(e)}")
            return ""
    
    def _obtener_clave_licencia(self, key):
        """Intenta obtener clave de licencia de varias ubicaciones posibles"""
        print("[DEBUG][PROGRAMAS] Buscando clave de licencia...")
        claves_posibles = [
            "ProductKey", "SerialKey", "LicenseKey", 
            "CDKey", "ActivationKey", "RegistrationKey"
        ]
        
        for clave in claves_posibles:
            try:
                valor, _ = winreg.QueryValueEx(key, clave)
                if valor:
                    print(f"[DEBUG][PROGRAMAS] Clave encontrada: {clave}")
                    return valor
            except OSError:
                continue
        
        # Buscar en otros lugares comunes
        try:
            install_path = self._obtener_valor_registro(key, "InstallLocation")
            if install_path:
                print(f"[DEBUG][PROGRAMAS] Buscando archivos de licencia en: {install_path}")
                for archivo in ["license.key", "serial.txt", "product.key"]:
                    ruta_archivo = os.path.join(install_path, archivo)
                    if os.path.exists(ruta_archivo):
                        with open(ruta_archivo, "r") as f:
                            contenido = f.read().strip()
                            if contenido:
                                print(f"[DEBUG][PROGRAMAS] Licencia encontrada en archivo")
                                return contenido
        except Exception as e:
            print(f"[ERROR][PROGRAMAS] Error al buscar licencia en archivos: {str(e)}")
        
        print("[DEBUG][PROGRAMAS] No se encontró clave de licencia")
        return ""

    def _convertir_tamano(self, size_kb):
        """Convierte tamaño de KB a formato legible"""
        print(f"[DEBUG][PROGRAMAS] Convirtiendo tamaño: {size_kb}")
        if not size_kb:
            print("[DEBUG][PROGRAMAS] Tamaño desconocido")
            return "Desconocido"
        try:
            size_kb = int(size_kb)
            if size_kb > 1024 * 1024:  # > 1 TB
                return f"{size_kb/(1024*1024):.2f} TB"
            elif size_kb > 1024:  # > 1 GB
                return f"{size_kb/1024:.2f} GB"
            else:
                return f"{size_kb} MB"
        except ValueError:
            print(f"[ERROR][PROGRAMAS] Error al convertir tamaño: {str(size_kb)}")
            return "Desconocido"

    def _obtener_paquetes_deb(self):
        """Obtiene paquetes .deb instalados"""
        print("[DEBUG][PROGRAMAS] Obteniendo paquetes DEB...")
        programas = []
        try:
            output = subprocess.check_output(
                "dpkg-query -W -f='${Package}||${Version}||${Maintainer}||${Installed-Size}\n'",
                shell=True,
                text=True
            )
            
            for linea in output.splitlines():
                if '||' in linea:
                    nombre, version, fabricante, tamano = linea.split('||', 3)
                    programas.append({
                        "nombre": nombre,
                        "version": version,
                        "fabricante": fabricante,
                        "licencia": self._obtener_licencia_debian(nombre),
                        "tamaño": f"{int(tamano) // 1024} MB" if tamano.isdigit() else "Desconocido"
                    })
            print(f"[DEBUG][PROGRAMAS] Paquetes DEB encontrados: {len(programas)}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR][PROGRAMAS] Error al ejecutar dpkg-query: {str(e)}")
        except Exception as e:
            print(f"[ERROR][PROGRAMAS] Error al procesar paquetes DEB: {str(e)}")
        return programas
    
    def _obtener_paquetes_rpm(self):
        """Obtiene paquetes RPM instalados"""
        print("[DEBUG][PROGRAMAS] Obteniendo paquetes RPM...")
        programas = []
        try:
            output = subprocess.check_output(
                "rpm -qa --qf '%{NAME}||%{VERSION}||%{VENDOR}||%{LICENSE}||%{SIZE}\n'",
                shell=True,
                text=True
            )
            
            for linea in output.splitlines():
                if '||' in linea:
                    nombre, version, fabricante, licencia, tamano = linea.split('||', 4)
                    programas.append({
                        "nombre": nombre,
                        "version": version,
                        "fabricante": fabricante,
                        "licencia": licencia,
                        "tamaño": f"{int(tamano) // 1024} KB"
                    })
            print(f"[DEBUG][PROGRAMAS] Paquetes RPM encontrados: {len(programas)}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR][PROGRAMAS] Error al ejecutar rpm: {str(e)}")
        except Exception as e:
            print(f"[ERROR][PROGRAMAS] Error al procesar paquetes RPM: {str(e)}")
        return programas
    
    def _obtener_paquetes_snap(self):
        """Obtiene paquetes Snap instalados"""
        print("[DEBUG][PROGRAMAS] Obteniendo paquetes SNAP...")
        programas = []
        try:
            output = subprocess.check_output(
                "snap list --all | awk 'NR>1 {print $1 \"||\" $2 \"||\" $5 \"||\" $6}'",
                shell=True,
                text=True
            )
            
            for linea in output.splitlines():
                if '||' in linea:
                    partes = linea.split('||')
                    if len(partes) >= 4:
                        nombre, version, notas, tamano = partes
                        programas.append({
                            "nombre": nombre,
                            "version": version,
                            "fabricante": "Snapcraft",
                            "licencia": "Desconocido",
                            "tamaño": tamano,
                            "tipo": "snap"
                        })
            print(f"[DEBUG][PROGRAMAS] Paquetes SNAP encontrados: {len(programas)}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR][PROGRAMAS] Error al ejecutar snap: {str(e)}")
        except Exception as e:
            print(f"[ERROR][PROGRAMAS] Error al procesar paquetes SNAP: {str(e)}")
        return programas
    
    def _obtener_paquetes_flatpak(self):
        """Obtiene paquetes Flatpak instalados"""
        print("[DEBUG][PROGRAMAS] Obteniendo paquetes FLATPAK...")
        programas = []
        try:
            output = subprocess.check_output(
                "flatpak list --app --columns=application,version,size | awk -F'\t' '{print $1 \"||\" $2 \"||\" $3}'",
                shell=True,
                text=True
            )
            
            for linea in output.splitlines():
                if '||' in linea:
                    nombre, version, tamano = linea.split('||', 2)
                    programas.append({
                        "nombre": nombre,
                        "version": version,
                        "fabricante": "Flatpak",
                        "licencia": "Desconocido",
                        "tamaño": tamano,
                        "tipo": "flatpak"
                    })
            print(f"[DEBUG][PROGRAMAS] Paquetes FLATPAK encontrados: {len(programas)}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR][PROGRAMAS] Error al ejecutar flatpak: {str(e)}")
        except Exception as e:
            print(f"[ERROR][PROGRAMAS] Error al procesar paquetes FLATPAK: {str(e)}")
        return programas