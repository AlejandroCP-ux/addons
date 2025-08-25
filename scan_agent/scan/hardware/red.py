# -*- coding: utf-8 -*-
import platform
import socket
import re
import psutil
from typing import List, Dict, Any

class RecolectorRed:
    """
    Clase mejorada para recolectar información de las interfaces de red físicas y activas.
    Utiliza psutil como fuente principal para garantizar la compatibilidad multiplataforma
    y se centra en el estado de la interfaz en lugar de solo su nombre.
    """
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.patrones_virtuales = [
            r'lo\b',              # Loopback (lo, lo0, etc.)
            r'docker',            # Docker
            r'veth',              # Virtual Ethernet
            r'br-',               # Bridge
            r'virbr',             # Virtual Bridge
            r'tun',               # Tunnels (VPN)
            r'tap',               # TAP interfaces
            r'vmnet',             # VMware
            r'vboxnet',           # VirtualBox
            r'ppp',               # PPP interfaces
            r'teredo',            # Teredo tunneling
            r'bluetooth',         # Bluetooth
            r'virtual',           # Nombres que contienen "Virtual"
            r'pseudo',            # Pseudo-interfaces
            r'hyper-v',           # Hyper-V
            r'isatap',            # ISATAP
        ]

    def obtener_info(self) -> List[Dict[str, Any]]:
        """
        Interfaz principal para obtener una lista de diccionarios con la información
        de las direcciones de red relevantes, ordenadas por prioridad.
        """
        if self.debug:
            print("[DEBUG][RED] Iniciando recolección de información de red...")

        ips_encontradas = self._obtener_ips_con_psutil()
        ips_ordenadas = self._ordenar_ips(ips_encontradas)

        if self.debug:
            print(f"[DEBUG][RED] Se encontraron {len(ips_ordenadas)} IPs relevantes y ordenadas.")
            for ip_info in ips_ordenadas:
                print(f"  [>] IP: {ip_info['ip']}, MAC: {ip_info['mac']}, Tipo: {ip_info['tipo']}, Interfaz: {ip_info['interfaz']}")

        return ips_ordenadas

    def _obtener_ips_con_psutil(self) -> List[Dict[str, Any]]:
        """
        Obtiene IPs de todas las interfaces usando psutil, filtrando por estado y nombre.
        Este método es multiplataforma.
        """
        ips_validas = []
        try:
            # 1. Obtener el estado de todas las interfaces (up, running, etc.)
            interfaces_stats = psutil.net_if_stats()
            # 2. Obtener las direcciones de todas las interfaces
            interfaces_addrs = psutil.net_if_addrs()

            for nombre, stats in interfaces_stats.items():
                if self._es_interfaz_relevante(nombre, stats):
                    # La interfaz es física y está activa, ahora buscamos su IP
                    for addr in interfaces_addrs.get(nombre, []):
                        # Buscamos la dirección IPv4
                        if addr.family == socket.AF_INET and self._es_ip_valida(addr.address):
                            mac = self._obtener_mac(interfaces_addrs.get(nombre, []))
                            tipo = self._determinar_tipo_interfaz(nombre)

                            ips_validas.append({
                                "ip": addr.address,
                                "mac": mac,
                                "tipo": tipo,
                                "interfaz": nombre,
                            })
                            if self.debug:
                                print(f"[DEBUG][RED] Interfaz válida encontrada: {nombre} ({tipo}) con IP {addr.address}")
                            # Solo nos interesa la primera IP válida por interfaz
                            break 
        except Exception as e:
            if self.debug:
                print(f"[ERROR][RED] Error al obtener IPs con psutil: {e}")

        return ips_validas

    def _es_interfaz_relevante(self, nombre: str, stats: Any) -> bool:
        """
        Determina si una interfaz es relevante.
        Una interfaz es relevante si está ACTIVA y NO es VIRTUAL.
        """
        # Criterio 1: La interfaz debe estar activa (es el filtro más importante)
        if not stats.isup:
            if self.debug:
                print(f"[DEBUG][RED] Interfaz '{nombre}' descartada (no está activa).")
            return False

        # Criterio 2: La interfaz no debe coincidir con patrones de nombres virtuales
        es_virtual = any(re.search(patron, nombre, re.IGNORECASE) for patron in self.patrones_virtuales)
        if es_virtual:
            if self.debug:
                print(f"[DEBUG][RED] Interfaz '{nombre}' descartada (marcada como virtual por nombre).")
            return False

        return True
    
    def _es_ip_valida(self, ip: str) -> bool:
        """Determina si una IP es una dirección IPv4 pública o privada válida."""
        # Filtra loopback y direcciones link-local de auto-configuración
        return not (ip.startswith("127.") or ip.startswith("169.254."))

    def _obtener_mac(self, direcciones: list) -> str:
        """Extrae la dirección MAC de una lista de direcciones de una interfaz."""
        for addr in direcciones:
            if addr.family == psutil.AF_LINK:
                return addr.address.upper().replace("-", ":")
        return "No encontrada"

    def _determinar_tipo_interfaz(self, nombre_interfaz: str) -> str:
        """Determina el tipo de interfaz (Ethernet, Wi-Fi) basándose en patrones de nombre."""
        nombre_lower = nombre_interfaz.lower()
        if any(keyword in nombre_lower for keyword in ['eth', 'enp', 'ens', 'eno', 'lan', 'ethernet', 'gigabit']):
            return "Ethernet"
        if any(keyword in nombre_lower for keyword in ['wlan', 'wlp', 'wlo', 'wi-fi', 'wireless']):
            return "Wi-Fi"
        return "Otro"

    def _ordenar_ips(self, ips: list) -> list:
        """Ordena las IPs por prioridad: Ethernet > Wi-Fi > Otros."""
        orden_prioridad = {"Ethernet": 1, "Wi-Fi": 2, "Otro": 3}
        return sorted(ips, key=lambda x: orden_prioridad.get(x["tipo"], 4))

# --- Ejemplo de uso ---
if __name__ == '__main__':
    print("Recolectando información de red (modo debug activado)...")
    recolector = RecolectorRed(debug=True)
    info_red = recolector.obtener_info()
    
    print("\n--- RESULTADO FINAL ---")
    if info_red:
        for net in info_red:
            print(f"Interfaz: {net['interfaz']} ({net['tipo']})")
            print(f"  ├─ IP:  {net['ip']}")
            print(f"  └─ MAC: {net['mac']}")
    else:
        print("No se encontraron interfaces de red activas y relevantes.")