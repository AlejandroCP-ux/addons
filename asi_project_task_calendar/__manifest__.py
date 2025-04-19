{
    'name': 'Tareas a Eventos',
    'version': '1.0',
    'category': 'Project Management',
    'author': 'Javier Escobar',
    'website': 'https://asisurl.cu',
    'license': 'AGPL-3',
    'summary': 'Crea eventos de calendario para las tareas de proyecto.',
    'description': """
Este módulo crea un evento de calendario para cada nueva tarea de proyecto,
asignándolo al responsable de la tarea. Al cerrar la tarea, el evento se marca como completado.
""",
    'depends': ['project','calendar'],
    'data': [
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
}
