# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions

class AddSoftwareFromListWizard(models.TransientModel):
    _name = 'profile.add_software.wizard'
    _description = 'Asistente para Añadir Software desde Lista Blanca a Perfil'

    # Campo para seleccionar la lista blanca. El dominio filtra para mostrar solo las de tipo 'white'.
    whitelist_id = fields.Many2one(
        'it.hw.list', 
        string="Lista Blanca", 
        required=True, 
        domain="[('type', '=', 'white')]",
        help="Seleccione la lista blanca de la cual desea importar el software."
    )

    def action_add_software(self):
        """
        Acción principal del wizard. Añade el software de la lista blanca seleccionada
        al perfil de usuario activo.
        """
        self.ensure_one()
        # Obtenemos el perfil activo desde el contexto
        profile = self.env['it.user.profile'].browse(self.env.context.get('active_id'))

        if not self.whitelist_id.software_ids:
            raise exceptions.UserError("La lista blanca seleccionada no contiene ningún software.")

        # IDs de software que ya están en el perfil
        current_software_ids = set(profile.softwares_ids.ids)
        
        # IDs de software de la lista blanca seleccionada
        whitelist_software_ids = set(self.whitelist_id.software_ids.ids)

        # Calculamos los IDs que son nuevos y necesitan ser añadidos
        new_software_ids = list(whitelist_software_ids - current_software_ids)
        
        added_count = len(new_software_ids)

        if added_count > 0:
            # Usamos el comando (4, id) para añadir los nuevos softwares sin borrar los existentes
            profile.write({'softwares_ids': [(4, sw_id) for sw_id in new_software_ids]})

        # Preparamos la notificación para el usuario
        notification = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Operación Completada',
                'message': f'Se han añadido {added_count} nuevos softwares al perfil "{profile.name}".',
                'sticky': False,
                'type': 'success' if added_count > 0 else 'warning',
            }
        }
        return notification