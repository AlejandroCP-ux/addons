# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ITUserProfile(models.Model):
    # _inherit = ['it.user.profile', 'incident.mixin']
    _inherit = 'it.user.profile'

    softwares_ids = fields.Many2many(
        "it.asset.software",
        relation='it_user_profile_software_rel', # Es buena práctica definir la tabla de relación
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

    @api.depends('user_ids', 'user_ids.hardware_ids')
    def _compute_hardware_ids(self):
        """
        Calcula y actualiza el hardware involucrado en el perfil.
        Maneja hardware compartido y evita duplicados.
        """
        for profile in self:
            # Si no hay usuarios, no hay hardware.
            if not profile.user_ids:
                profile.hardware_ids = [(5, 0, 0)] # Comando para limpiar la relación
                continue

            # Recolecta todos los IDs de hardware de todos los usuarios del perfil
            all_hardware_ids = self.env['it.asset.hardware']
            for user in profile.user_ids:
                all_hardware_ids |= user.hardware_ids
            
            # El ORM de Odoo maneja automáticamente los duplicados.
            # Usamos el comando (6, 0, [IDs]) para reemplazar la lista existente.
            profile.hardware_ids = [(6, 0, all_hardware_ids.ids)]

    def write(self, vals):
        """
        Sobreescribimos 'write' para ser el punto de entrada de toda nuestra lógica
        de automatización y creación de incidentes.
        """
        # Guardamos el estado anterior para comparaciones
        original_softwares = {p.id: set(p.softwares_ids.ids) for p in self}
        original_users = {p.id: set(p.user_ids.ids) for p in self}

        # Ejecutamos la operación de escritura original
        res = super().write(vals)

        for profile in self:
            # 1. INCIDENTES POR CAMBIOS EN SOFTWARE PERMITIDO
            new_softwares = set(profile.softwares_ids.ids)
            if new_softwares != original_softwares.get(profile.id):
                profile._create_incident(
                    title=f"Cambio de software en perfil: {profile.name}",
                    description=f"La lista de software permitido para el perfil '{profile.name}' ha sido modificada.",
                    severity='info',
                    asset_ref=profile
                )
                # Tras un cambio, siempre es bueno re-evaluar la conformidad
                profile.action_check_compliance()

            # 2. INCIDENTES POR CAMBIOS EN USUARIOS (y recalculo de hardware)
            new_users = set(profile.user_ids.ids)
            if new_users != original_users.get(profile.id):
                profile._create_incident(
                    title=f"Cambio de usuarios en perfil: {profile.name}",
                    description=f"La lista de usuarios para el perfil '{profile.name}' ha sido modificada. El hardware asociado puede haber cambiado.",
                    severity='info',
                    asset_ref=profile
                )
                # El compute se dispara solo, pero la revisión de compliance la llamamos nosotros
                profile.action_check_compliance()
        
        return res

    def action_check_compliance(self):
        """
        Acción para verificar la conformidad del software en todo el hardware
        asociado al perfil.
        """
        self.ensure_one()
        
        # Obtenemos todo el software prohibido de las listas negras ACTIVAS
        blacklisted_sw_ids = self.env['it.hw.list'].search([
            ('type', '=', 'black'),
            ('active', '=', True)
        ]).mapped('software_ids')

        allowed_sw_ids = self.softwares_ids

        for hw in self.hardware_ids:
            # Asumimos que el hardware tiene un campo 'software_ids' que lista el software instalado
            if not hasattr(hw, 'software_ids'):
                continue

            installed_sw_ids = hw.software_ids

            for software in installed_sw_ids:
                # CASO 1: Software está en la lista negra (ALTA SEVERIDAD)
                if software in blacklisted_sw_ids:
                    self._create_incident(
                        title=f"Software Prohibido Detectado: {software.name}",
                        description=f"El software prohibido '{software.name}' fue detectado en el hardware '{hw.name}' "
                                    f"asociado al perfil '{self.name}'.",
                        severity='high',
                        asset_ref=hw
                    )
                # CASO 2: Software no está ni permitido ni prohibido (MEDIA SEVERIDAD)
                elif software not in allowed_sw_ids:
                    self._create_incident(
                        title=f"Software No Gestionado Detectado: {software.name}",
                        description=f"El software no gestionado '{software.name}' (ni permitido ni prohibido) fue detectado "
                                    f"en el hardware '{hw.name}' asociado al perfil '{self.name}'.",
                        severity='medium',
                        asset_ref=hw
                    )
        
        # Notificación al usuario
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Comprobación Completada'),
                'message': _('Se ha completado la comprobación de conformidad de software para el perfil %s.') % self.name,
                'sticky': False,
                'type': 'success'
            }
        }