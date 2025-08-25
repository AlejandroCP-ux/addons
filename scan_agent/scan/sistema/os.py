import platform

class RecolectorOS:
    def obtener_info(self):
        return {
            "sistema": platform.system(),
            "version": platform.version(),
            "release": platform.release(),
            "edicion": " ".join(platform.win32_ver())
        }