# -*- coding: utf-8 -*-
{
    "name": "Performance Evaluation Summary",
    "version": "16.0.1.0.0",
    "summary": "Resumen de evaluaciones de subordinados por periodo (fixes)",
    "description": "Extiende el módulo de Performance Evaluation y añade un wizard para imprimir un resumen de evaluaciones de los subordinados de un empleado para un período determinado. Esta versión incluye correcciones de templates y permisos.",
    "author": "ChatGPT for user",
    "category": "Human Resources",
    "depends": ["performance_evaluation", "hr"],
    "data": [
        "security/ir.model.access.csv",
        "views/performance_evaluation_summary_views.xml",
        "data/menu.xml",
        "reports/performance_evaluation_summary_report.xml",
        "reports/performance_evaluation_summary_template.xml"
    ],
    "installable": True,
    "application": False,
}
