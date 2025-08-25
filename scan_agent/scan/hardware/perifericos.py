import platform
import re
import sys
import traceback

class RecolectorPerifericos:
    """
    Clase encargada de recolectar información sobre periféricos (teclado, mouse, monitor)
    del sistema operativo, con soporte para Windows y Linux.
    """
    def obtener_info(self):
        """
        Punto de entrada principal. Detecta el sistema operativo y llama al método correspondiente.
        """
        try:
            sistema = platform.system()
            print(f"[DEBBUG][Perifericos] Sistema detectado: {sistema}", file=sys.stderr)
            
            if sistema == "Windows":
                return self._obtener_info_windows()
            elif sistema == "Linux":
                return self._obtener_info_linux()
            else:
                print(f"[DEBBUG][Perifericos] Sistema operativo {sistema} no soportado", file=sys.stderr)
                return []
        except Exception as e:
            print(f"[DEBBUG][Perifericos] Error general: {str(e)}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return []

    def _obtener_info_windows(self):
        """
        Recolecta información de periféricos en un sistema Windows usando WMI.
        """
        try:
            import win32com.client
            perifericos = []
            wmi = win32com.client.GetObject("winmgmts:")
            
            print("[DEBBUG][Perifericos] Buscando dispositivos en Windows...", file=sys.stderr)
            
            # --- Recolección de Ratones ---
            dispositivos_raton = list(wmi.InstancesOf("Win32_PointingDevice"))
            print(f"[DEBBUG][Perifericos] Encontrados {len(dispositivos_raton)} ratones", file=sys.stderr)
            
            for item in dispositivos_raton:
                try:
                    nombre = self._get_prop(item, 'Name')
                    valido = self._es_dispositivo_valido(nombre, "Mouse")
                    print(f"[DEBBUG][Perifericos] Ratón: '{nombre}' - Válido: {valido}", file=sys.stderr)
                    
                    if valido:
                        perifericos.append({
                            "tipo": "Mouse",
                            "nombre": nombre,
                            "fabricante": self._get_prop(item, 'Manufacturer', 'Desconocido'),
                            "id_dispositivo": self._get_prop(item, 'DeviceID'),
                            "pnp_id": self._get_prop(item, 'PNPDeviceID'),
                            "es_usb": "USB" in self._get_prop(item, 'PNPDeviceID', '').upper()
                        })
                except Exception as e:
                    print(f"[DEBBUG][Perifericos] Error procesando ratón: {str(e)}", file=sys.stderr)

            # --- Recolección de Teclados con Lógica de Fallback ---
            dispositivos_teclado = list(wmi.InstancesOf("Win32_Keyboard"))
            print(f"[DEBBUG][Perifericos] Encontrados {len(dispositivos_teclado)} teclados", file=sys.stderr)
            
            teclados_validos = []
            teclados_genericos = []

            for item in dispositivos_teclado:
                try:
                    nombre = self._get_prop(item, 'Name')
                    teclado_info = {
                        "tipo": "Teclado",
                        "nombre": nombre,
                        "fabricante": self._get_prop(item, 'Manufacturer', 'Desconocido'),
                        "id_dispositivo": self._get_prop(item, 'DeviceID'),
                        "pnp_id": self._get_prop(item, 'PNPDeviceID'),
                        "es_usb": "USB" in self._get_prop(item, 'PNPDeviceID', '').upper()
                    }
                    
                    if self._es_dispositivo_valido(nombre, "Teclado"):
                        print(f"[DEBBUG][Perifericos] Teclado: '{nombre}' - Válido: True", file=sys.stderr)
                        teclados_validos.append(teclado_info)
                    else:
                        print(f"[DEBBUG][Perifericos] Teclado: '{nombre}' - Válido: False (candidato a genérico)", file=sys.stderr)
                        teclados_genericos.append(teclado_info)
                except Exception as e:
                    print(f"[DEBBUG][Perifericos] Error procesando teclado: {str(e)}", file=sys.stderr)

            if teclados_validos:
                print(f"[DEBBUG][Perifericos] Añadiendo {len(teclados_validos)} teclado(s) válido(s).", file=sys.stderr)
                perifericos.extend(teclados_validos)
            elif teclados_genericos:
                print("[DEBBUG][Perifericos] No se encontraron teclados válidos. Añadiendo un teclado genérico como respaldo.", file=sys.stderr)
                perifericos.append(teclados_genericos[0]) # Añadir solo el primero como fallback
            
            # --- Recolección de Monitores ---
            try:
                monitores_encontrados = {}
                
                # Enfoque 1: Win32_DesktopMonitor (fiable para monitores físicos activos)
                monitores_desktop = list(wmi.InstancesOf("Win32_DesktopMonitor"))
                print(f"[DEBBUG][Perifericos] Encontrados {len(monitores_desktop)} monitores (Win32_DesktopMonitor)", file=sys.stderr)
                
                for item in monitores_desktop:
                    nombre = self._get_prop(item, 'Name')
                    pnp_id = self._get_prop(item, 'PNPDeviceID')
                    if not pnp_id or not self._es_dispositivo_valido(nombre, "Monitor"):
                        print(f"[DEBBUG][Perifericos] Monitor (DesktopMonitor) descartado: '{nombre}'", file=sys.stderr)
                        continue
                    
                    if pnp_id not in monitores_encontrados:
                         print(f"[DEBBUG][Perifericos] Monitor (DesktopMonitor) añadido: '{nombre}'", file=sys.stderr)
                         monitores_encontrados[pnp_id] = {
                            "tipo": "Monitor", "nombre": nombre,
                            "fabricante": self._get_prop(item, 'MonitorManufacturer', 'Desconocido'),
                            "modelo": self._get_prop(item, 'MonitorType', 'Desconocido'),
                            "tamano": f"{self._get_prop(item, 'ScreenWidth', 0)}x{self._get_prop(item, 'ScreenHeight', 0)}",
                            "id_dispositivo": self._get_prop(item, 'DeviceID'), "pnp_id": pnp_id
                        }

                # Enfoque 2: Win32_PnPEntity (para más detalles y cubrir casos borde)
                query_monitores_pnp = "SELECT * FROM Win32_PnPEntity WHERE PNPClass = 'Monitor' AND DeviceID LIKE '%DISPLAY%'"
                monitores_pnp = wmi.ExecQuery(query_monitores_pnp)
                print(f"[DEBBUG][Perifericos] Encontrados {len(monitores_pnp)} monitores (Win32_PnPEntity con filtro)", file=sys.stderr)
                
                for item in monitores_pnp:
                    pnp_id = self._get_prop(item, 'DeviceID', '')
                    nombre = self._get_prop(item, 'Name')
                    
                    if pnp_id and pnp_id not in monitores_encontrados and not pnp_id.upper().startswith('ROOT\\'):
                        if not self._es_dispositivo_valido(nombre, "Monitor"):
                            print(f"[DEBBUG][Perifericos] Monitor PnP descartado por nombre: '{nombre}'", file=sys.stderr)
                            continue
                            
                        print(f"[DEBBUG][Perifericos] Monitor PnP añadido: '{nombre}'", file=sys.stderr)
                        fabricante, modelo = self._extraer_info_de_pnp_id(pnp_id)
                        monitores_encontrados[pnp_id] = {
                            "tipo": "Monitor", "nombre": nombre,
                            "fabricante": fabricante if fabricante != "Desconocido" else self._get_prop(item, 'Manufacturer', 'Desconocido'),
                            "modelo": modelo, "id_dispositivo": pnp_id, "pnp_id": pnp_id
                        }
                
                perifericos.extend(monitores_encontrados.values())

            except Exception as e:
                print(f"[DEBBUG][Perifericos] Error obteniendo monitores: {str(e)}", file=sys.stderr)
            
            # --- Procesamiento Final y Desduplicación ---
            perifericos_finales = self._procesar_y_desduplicar(perifericos)
            
            print(f"[DEBBUG][Perifericos] Total dispositivos válidos: {len(perifericos_finales)}", file=sys.stderr)
            if perifericos_finales:
                print("[DEBBUG][Perifericos] Dispositivos recolectados:", file=sys.stderr)
                for i, p in enumerate(perifericos_finales, 1):
                    tipo = p.get('tipo', 'Desconocido')
                    nombre = p.get('nombre', 'Sin nombre')
                    id_disp = p.get('pnp_id', p.get('id_dispositivo', 'N/A'))[:50]
                    print(f"  {i}. {tipo}: {nombre} (ID: {id_disp}...)", file=sys.stderr)
            
            return perifericos_finales
        
        except ImportError:
            print("[DEBBUG][Perifericos] ERROR: Módulo win32com no disponible. Instale con: pip install pywin32", file=sys.stderr)
            return []
        except Exception as e:
            print(f"[DEBBUG][Perifericos] ERROR en Windows: {str(e)}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return []

    def _get_prop(self, obj, prop_name, default=''):
        """Obtiene una propiedad de un objeto WMI de forma segura."""
        try:
            value = getattr(obj, prop_name)
            return value if value is not None else default
        except AttributeError:
            return default

    def _es_dispositivo_valido(self, nombre, tipo):
        """
        Valida si un nombre de dispositivo corresponde a un periférico físico real,
        excluyendo controladores virtuales y genéricos.
        """
        if not nombre or nombre.lower() == 'desconocido':
            return False
            
        nombre_lower = nombre.lower()
        
        patrones_excluir_comunes = [
            r'virtual', r'virtu', r'root', r'default', r'controlador', 
            r'compatible con hid', r'hid-compliant'
        ]
        if any(re.search(patron, nombre_lower) for patron in patrones_excluir_comunes):
            return False

        if tipo == "Mouse":
            patrones_incluir = [r'usb', r'bluetooth', r'wireless', r'mouse']
        elif tipo == "Teclado":
            patrones_excluir = [r'mejorado\s*\(\d+\s*ó\s*\d+\s*teclas\)', r'dispositivo de teclado hid']
            if any(re.search(patron, nombre_lower) for patron in patrones_excluir):
                return False
            patrones_incluir = [r'usb', r'bluetooth', r'wireless', r'keyboard']
        elif tipo == "Monitor":
            patrones_excluir = [r'basic display', r'generic non-pnp', r'pnp genérico no']
            if any(re.search(patron, nombre_lower) for patron in patrones_excluir):
                return False
            patrones_incluir = [r'pnp', r'plug and play', r'monitor']
        else:
            return True

        marcas_conocidas = [
            r'logitech', r'microsoft', r'razer', r'steelseries', r'corsair',
            r'dell', r'hp', r'lenovo', r'samsung', r'lg', r'aoc', r'benq', 'asus'
        ]
        if any(re.search(marca, nombre_lower) for marca in marcas_conocidas):
            return True

        if any(re.search(patron, nombre_lower) for patron in patrones_incluir):
            return True
            
        # Aceptar nombres genéricos si no fueron explícitamente excluidos
        if "dispositivo de entrada usb" in nombre_lower:
            return True

        return False

    def _procesar_y_desduplicar(self, dispositivos):
        """
        Procesa la lista de dispositivos candidatos para eliminar duplicados,
        dando prioridad a los más específicos (ej. USB sobre otros).
        """
        if not dispositivos:
            return []
            
        dispositivos_finales = []
        pnp_ids_vistos = set()

        # Priorizar dispositivos por tipo y especificidad (USB)
        dispositivos.sort(key=lambda d: (
            d['tipo'] != 'Teclado', # Procesar teclados primero
            d['tipo'] != 'Mouse',   # Luego ratones
            d['tipo'] != 'Monitor', # Luego monitores
            not d.get('es_usb', False) # Dar prioridad a los USB dentro de cada tipo
        ))
        
        for dispositivo in dispositivos:
            pnp_id = dispositivo.get('pnp_id')
            
            # Usar pnp_id como clave única si está disponible
            if pnp_id and pnp_id in pnp_ids_vistos:
                print(f"[DEBBUG][Perifericos] Dispositivo duplicado (PNP ID) descartado: {dispositivo['tipo']}: {dispositivo['nombre']}", file=sys.stderr)
                continue
            
            dispositivos_finales.append(dispositivo)
            if pnp_id:
                pnp_ids_vistos.add(pnp_id)
        
        return dispositivos_finales

    def _extraer_info_de_pnp_id(self, pnp_id):
        """Intenta extraer fabricante y modelo a partir de un PnP ID de monitor."""
        try:
            partes = pnp_id.split('\\')
            if len(partes) > 1:
                fabricante_codigo = partes[1]
                fabricantes = {"LEN": "Lenovo", "DEL": "Dell", "SAM": "Samsung", "LGD": "LG Display", "AOC": "AOC", "PHL": "Philips", "BNQ": "BenQ", "AUO": "AU Optronics", "IVM": "IBM", "GSM": "LG Electronics"}
                prefijo = fabricante_codigo[:3].upper()
                fabricante = fabricantes.get(prefijo, prefijo)
                modelo = fabricante_codigo[3:] if len(fabricante_codigo) > 3 else "Desconocido"
                return fabricante, modelo
        except:
            pass
        return "Desconocido", "Desconocido"

    def _obtener_info_linux(self):
        try:
            print("[DEBBUG][Perifericos] Intentando recolectar periféricos en Linux", file=sys.stderr)
            import pyudev
            perifericos = []
            context = pyudev.Context()
            
            # Dispositivos de entrada (ratones, teclados)
            for device in context.list_devices(subsystem='input'):
                # CORRECCIÓN: Usar el nuevo nombre del método
                if not self._es_dispositivo_valido_linux(device.get('NAME', '')):
                    continue
                
                tipo = self._determinar_tipo_linux(device)
                if not tipo:
                    continue
                
                parent = device.find_parent(subsystem='usb')
                periferico = {
                    "tipo": tipo,
                    "nombre": device.get('NAME', '').strip('"'),
                    "fabricante": device.get('ID_VENDOR_FROM_DATABASE', ''),
                    "modelo": device.get('ID_MODEL_FROM_DATABASE', ''),
                    "id_dispositivo": device.get('DEVNAME', ''),
                    "id_vendor": device.get('ID_VENDOR_ID', ''),
                    "id_model": device.get('ID_MODEL_ID', ''),
                    "serial": parent.get('ID_SERIAL_SHORT', '') if parent else ''
                }
                perifericos.append(periferico)
            
            # Monitores
            for device in context.list_devices(subsystem='drm'):
                if device.device_type != 'drm_minor' or not device.get('DEVNAME', '').startswith('card'):
                    continue
                
                edid = device.get('EDID', '')
                modelo = self._extraer_modelo_monitor(edid)
                fabricante = self._extraer_fabricante_monitor(edid)
                
                if modelo or fabricante:
                    perifericos.append({
                        "tipo": "Monitor",
                        "nombre": device.get('ID_MODEL_FROM_DATABASE', ''),
                        "fabricante": fabricante,
                        "modelo": modelo,
                        "id_dispositivo": device.get('DEVNAME', '')
                    })
            
            return perifericos
        
        except ImportError:
            print("Módulo pyudev no disponible. Usando alternativa para Linux")
            return []
        except Exception as e:
            print(f"[DEBBUG][Perifericos] Error en Linux: {str(e)}", file=sys.stderr)
            print(f"Error obteniendo periféricos en Linux: {str(e)}")
            return []

    def _es_dispositivo_valido_linux(self, nombre):
        """Filtra dispositivos virtuales y no válidos (versión Linux)"""
        if not nombre:
            return False
            
        patrones_excluir = [
            r'virtual', r'virtu', r'hid', r'composite', 
            r'root', r'default', r'generic', r'ps/2', 
            r'standard', r'pnp'
        ]
        
        nombre_lower = nombre.lower()
        return not any(patron in nombre_lower for patron in patrones_excluir)

    def _determinar_tipo_linux(self, device):
        propiedades = device.get('PROP', '')
        if 'mouse' in propiedades.lower():
            return "Mouse"
        elif 'keyboard' in propiedades.lower():
            return "Teclado"
        return None

    def _extraer_fabricante_monitor(self, edid):
        if not edid or len(edid) < 8:
            return ""
        # Los primeros 3 bytes del EDID contienen el ID del fabricante
        fabricante_id = edid[8:11].decode('ascii', errors='ignore')
        return fabricante_id

    def _extraer_modelo_monitor(self, edid):
        if not edid or len(edid) < 20:
            return ""
        # Los bytes 12-15 contienen el ID del modelo
        modelo_id = int.from_bytes(edid[12:16], byteorder='little')
        return f"{modelo_id:04X}"