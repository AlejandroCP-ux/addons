# Asumo que las importaciones de hardware, etc. están correctas
from ..hardware.cpu import RecolectorCPU
from ..hardware.ram import RecolectorRAM
from ..hardware.disco import RecolectorDiscos
from ..hardware.gpu import RecolectorGPU
from ..hardware.red import RecolectorRed
from ..hardware.perifericos import RecolectorPerifericos
from ..hardware.placamadre import RecolectorPlacaMadre
from .exportador import ExportadorOdoo
from ..sistema.os import RecolectorOS
from ..sistema.programas import RecolectorProgramas
import wmi
import platform
import hashlib
import logging

class GestorTI:
    def __init__(self, software_installed=False, network_installed=False):
        """
        Inicializa el gestor y decide qué recolectores usar
        basado en los módulos instalados en Odoo.
        """
        self.recolectores = {
            # Los de hardware siempre se recolectan
            "placa_madre": RecolectorPlacaMadre(),
            "cpu": RecolectorCPU(),
            "almacenamiento": RecolectorDiscos(),
            "ram": RecolectorRAM(),
            "gpu": RecolectorGPU(),
            "perifericos": RecolectorPerifericos(),
            "sistema_operativo": RecolectorOS(),
        }
        
        # Recolección condicional
        if software_installed:
            logging.info("El módulo de software está instalado. Se recolectarán los programas.")
            self.recolectores["programas"] = RecolectorProgramas()
        else:
            logging.warning("El módulo de software no está instalado. Se omitirá la recolección de programas.")

        if network_installed:
            logging.info("El módulo de red está instalado. Se recolectará la información de red.")
            self.recolectores["red"] = RecolectorRed(debug=True)
        else:
            logging.warning("El módulo de red no está instalado. Se omitirá la recolección de información de red.")

        self.exportador = None

    def set_exportador(self, exportador: ExportadorOdoo):
        """Asigna una instancia pre-configurada y probada del exportador."""
        self.exportador = exportador

    def recolectar_todo(self):
        resultados = {}
        for nombre, recolector in self.recolectores.items():
            try:
                if nombre == "perifericos":
                    perifericos = recolector.obtener_info()
                    resultados[nombre] = [self._generar_id_periferico(p) for p in perifericos]      
                elif nombre == "ram":
                    # Crear conexión WMI
                    c = wmi.WMI()

                    # Extraer serial de la motherboard y guardar en variable
                    motherboard_serial = next((board.SerialNumber.strip() for board in c.Win32_BaseBoard()), "UNKNOWN")
                    pc_identifier = f"{platform.node()}_{motherboard_serial}"
                    ram = recolector.obtener_info()
                    resultados[nombre] = [self._generar_id_local_ram(p, pc_identifier) for p in ram]     
                else:
                    resultados[nombre] = recolector.obtener_info()
            except Exception as e:
                resultados[nombre] = {"error": str(e)}
        return resultados


    def _generar_id_local_ram(self, ram, motherboard_serial):
        """
        Genera un ID local único y robusto para un módulo de RAM en una PC específica.

        La función prioriza el número de serie de la RAM por ser el identificador más
        confiable. Si el número de serie no está disponible o parece genérico, 
        crea un identificador "débil" a partir de otras propiedades de la RAM.

        Luego, combina este identificador de la RAM con el número de serie de la
        placa madre para crear un hash final que representa el vínculo único
        entre ese componente y esa PC.

        Args:
            ram (dict): Un diccionario con las propiedades de la RAM.
                        Debe contener 'Número de Serie' y otros detalles.
            motherboard_serial (str): El número de serie de la placa madre.

        Returns:
            str: Un hash SHA256 que representa el vínculo único RAM-PC.
        """
        ram_serial = ram.get('Número de Serie', '').strip()

        # Paso 1: Determinar el identificador más único posible para la RAM.
        # Se prioriza el número de serie si parece válido.
        # Un serial válido no debería ser '0', 'N/A' o un placeholder.
        if ram_serial and ram_serial not in ['0', 'N/A', 'SerNum'] and len(ram_serial) > 4:
            # Se considera un número de serie válido. Es el mejor identificador.
            id_unico_ram = ram_serial
        else:
            # Fallback: Si no hay número de serie, se crea un ID "débil" con otras propiedades.
            # ADVERTENCIA: Esto aumenta el riesgo de colisiones entre RAMs idénticas.
            id_unico_ram = (f"{ram.get('Fabricante', '')}-{ram.get('Modelo', '')}-"
                            f"{ram.get('Tamaño (GB)', '')}-{ram.get('Banco', '')}-{ram.get('Slot', '')}")

        # Paso 2: Crear el hash combinado con el serial de la placa madre.
        # Normalizar datos (a minúsculas y sin espacios) para consistencia.
        datos_para_hash = (f"ram_id:{id_unico_ram.lower()}-"
                        f"mb_serial:{str(motherboard_serial).strip().lower()}")
        
        hash_final = hashlib.sha256(datos_para_hash.encode('utf-8')).hexdigest()
        
        return {**ram, "id_unico": hash_final}
    
    def _generar_id_periferico(self, periferico):
        datos_id = f"{periferico.get('tipo', '')}-{periferico.get('id_dispositivo', '')}-{periferico.get('serial', '')}"
        hash_id = hashlib.sha256(datos_id.encode()).hexdigest()
        return {**periferico, "id_unico": hash_id}

    def exportar_datos(self):
        """Orquesta la recolección y exportación de todos los datos como un único activo."""
        if not self.exportador:
            logging.error("El exportador no está configurado. No se pueden enviar datos.")
            raise Exception("Exportador no configurado")

        logging.info("Recolectando todos los datos para la exportación...")
        datos_completos = self.recolectar_todo()

        # Nueva lógica: enviar todo el paquete de datos al exportador
        self.exportador.exportar_activo_completo(datos_completos)

    def test(self):
        """Función de prueba que recolecta y muestra la información por consola"""
        print("\n" + "="*50)
        print("INICIO DE PRUEBA DEL GESTOR DE TI")
        print("="*50)
        datos = self.recolectar_todo()
        self.imprimir_datos(datos)
        print("\n" + "="*50)
        print("PRUEBA COMPLETADA")
        print("="*50)
        
    def imprimir_datos(self, datos):
        """Imprime los datos recolectados de forma estructurada."""
        for categoria, info in datos.items():
            print(f"\n[{categoria.upper()}]")
            if isinstance(info, list):
                for item in info:
                    self._imprimir_diccionario(item)
            elif isinstance(info, dict):
                self._imprimir_diccionario(info)

    def _imprimir_diccionario(self, datos, indent=2):
        for clave, valor in datos.items():
            print(f"{' ' * indent}{clave}: {valor}")