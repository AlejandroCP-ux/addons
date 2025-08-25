# -*- coding: utf-8 -*-
from odoo import models

class IncidentMixin(models.AbstractModel):
    _name = 'incident.mixin'
    _description = 'Mixin para la Creación de Incidentes de TI'

    def _create_incident(self, title, description, severity, asset_ref=None):
        """
        Crea un nuevo incidente de TI.
        :param title: Título del incidente.
        :param description: Descripción detallada.
        :param severity: Severidad ('info', 'low', 'medium', 'high').
        :param asset_ref: Registro de Odoo relacionado (ej: un perfil, un hardware).
        """
        incident_vals = {
            'title': title,
            'description': description,
            'severity': severity,
        }
        if asset_ref:
            # Crea la referencia como 'modelo,id'
            incident_vals['asset_ref'] = f'{asset_ref._name},{asset_ref.id}'
            
        return self.env['it.incident'].create(incident_vals)