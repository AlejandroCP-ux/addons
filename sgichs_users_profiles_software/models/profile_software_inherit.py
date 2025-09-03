# RUTA: sgichs_users_profiles_software/models/profile_software_inherit.py (CÓDIGO ACTUALIZADO)

# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ITUserProfile(models.Model):
    # Heredamos del modelo 'it.user.profile' que ya tiene su propia lógica de incidentes.
    _inherit = 'it.user.profile'

    softwares_ids = fields.Many2many(
        "it.asset.software",
        relation='it_user_profile_software_rel',
        column1='profile_id',
        column2='software_id',
        string='Software Permitido',
        tracking=True,
        help='Software que pueden utilizar los usuarios que pertenezcan a este perfil'
    )

    hardware_ids = fields.Many2many(
        'it.asset.hardware',
        string='Hardware Involucrado',
        compute='_compute_hardware_ids',
        store=True,
        help="Hardware asignado a los usuarios de este perfil. Se actualiza automáticamente."
    )

    @api.depends('user_ids', 'user_ids.hardware_ids')
    def _compute_hardware_ids(self):
        """
        Calcula y actualiza el hardware involucrado en el perfil.
        """
        for profile in self:
            if not profile.user_ids:
                profile.hardware_ids = [(5, 0, 0)]
                continue
            
            all_hardware_ids = self.env['it.asset.hardware'].browse()
            for user in profile.user_ids:
                all_hardware_ids |= user.hardware_ids
            
            profile.hardware_ids = [(6, 0, all_hardware_ids.ids)]

    def action_check_compliance(self):
        """
        Verifica la conformidad de todo el software permitido en este perfil
        y genera los incidentes correspondientes.
        """
        self.ensure_one()
        
        # Obtener el modelo que contiene la lógica de verificación
        hw_list_model = self.env['it.hw.list']
        
        # Verificar si el modelo de incidentes está instalado para evitar errores
        if 'it.incident' not in self.env:
            raise models.UserError(_("El módulo de gestión de incidentes (sgichs_core2) no parece estar completamente cargado o instalado."))

        softwares_to_check = self.softwares_ids
        if not softwares_to_check:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Software'),
                    'message': _('Este perfil no tiene software para verificar.'),
                    'type': 'warning',
                }
            }

        incidents_before = self.env['it.incident'].search_count([])
        
        # Iterar sobre el software del perfil y verificar cada uno
        for software in softwares_to_check:
            # Llamamos a la lógica que ya existe en el modelo it.hw.list
            # Pasamos el ID del software y dejamos hardware_id como None, ya que es una verificación a nivel de perfil.
            hw_list_model.check_software_compliance(software.id, hardware_id=None)
            
        incidents_after = self.env['it.incident'].search_count([])
        new_incidents_count = incidents_after - incidents_before
        
        # Notificar al usuario sobre el resultado
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Verificación Completada'),
                'message': _('Se han creado %d nuevos incidentes de conformidad.') % new_incidents_count,
                'type': 'success',
            }
        }

    def write(self, vals):
        """
        Extendemos 'write' para añadir lógica de incidentes específica
        para los cambios de software.
        """
        original_softwares = {p.id: p.softwares_ids for p in self}

        # La llamada a super() ejecutará la lógica de incidentes del modelo padre
        res = super().write(vals)

        if 'softwares_ids' in vals:
            for profile in self:
                old_sw_set = set(original_softwares.get(profile.id).ids)
                new_sw_set = set(profile.softwares_ids.ids)
                
                added = self.env['it.asset.software'].browse(list(new_sw_set - old_sw_set))
                removed = self.env['it.asset.software'].browse(list(old_sw_set - new_sw_set))

                changes_info = []
                if added:
                    changes_info.append(_("Software Permitido Añadido: %s", ", ".join(added.mapped('name'))))
                if removed:
                    changes_info.append(_("Software Permitido Eliminado: %s", ", ".join(removed.mapped('name'))))
                
                if changes_info:
                    # Usamos el método del padre para crear el incidente
                    profile._log_profile_changes_as_incident(
                        'write', 
                        "\n".join(changes_info)
                    )
        return res