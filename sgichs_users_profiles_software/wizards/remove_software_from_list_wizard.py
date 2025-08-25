# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class RemoveSoftwareFromListWizard(models.TransientModel):
    _name = 'profile.remove_software.wizard'
    _description = 'Asistente para Quitar Software desde una Lista'

    list_id = fields.Many2one(
        'it.hw.list', 
        string="Lista de Software", 
        required=True,
        help="Seleccione una lista. El software en común con el perfil será eliminado."
    )
    
    
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

    def action_remove_software(self):
        """
        Elimina el software de la lista seleccionada que también exista en el perfil.
        """
        self.ensure_one()
        profile = self.env['it.user.profile'].browse(self.env.context.get('active_id'))

        if not self.list_id.software_ids:
            # Simplemente notificar y cerrar, no es un error.
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Lista Vacía'),
                    'message': _('La lista seleccionada no contiene software.'),
                    'type': 'warning',
                }
            }

        # IDs de software que están en el perfil
        profile_software_ids = set(profile.softwares_ids.ids)
        
        # IDs de software en la lista seleccionada
        list_software_ids = set(self.list_id.software_ids.ids)

        # Calculamos la intersección: los IDs a eliminar
        software_to_remove_ids = list(profile_software_ids.intersection(list_software_ids))
        
        removed_count = len(software_to_remove_ids)

        if removed_count > 0:
            # Usamos el comando (3, id) para desvincular cada software
            commands = [(3, sw_id) for sw_id in software_to_remove_ids]
            profile.write({'softwares_ids': commands})
            
            # Creamos el incidente informativo
            self._create_incident(
                title=f"Software eliminado en masa del perfil: {profile.name}",
                description=f"Se eliminaron {removed_count} softwares del perfil '{profile.name}' "
                            f"usando la lista '{self.list_id.name}'.",
                severity='info',
                asset_ref=profile
            )

        # Notificación para el usuario
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Operación Completada'),
                'message': _('Se han quitado %d softwares del perfil "%s".') % (removed_count, profile.name),
                'sticky': False,
                'type': 'success' if removed_count > 0 else 'info',
            }
        }