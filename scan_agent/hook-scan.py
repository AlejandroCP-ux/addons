# hook-scan.py
# Ayuda a PyInstaller a encontrar los módulos dinámicos
hiddenimports = [
    'scan.core',
    'scan.hardware',
    'scan.sistema',
    'scan.core.recolector',
    'scan.core.exportador',
    'scan.hardware.cpu',
    'scan.hardware.disco',
    'scan.hardware.gpu',
    'scan.hardware.perifericos',
    'scan.hardware.ram',
    'scan.hardware.red',
    'scan.sistema.os',
    'scan.sistema.programas',
    'scan.sistema.updates'
]