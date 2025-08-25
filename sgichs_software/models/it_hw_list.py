from odoo import models, fields, api, exceptions
import logging
import datetime

_logger = logging.getLogger(__name__)

class HWList(models.Model):
    _name = 'it.hw.list'
    _description = 'Lista de Control de Software'

    name = fields.Char(string="Nombre de la Lista", required=True)
    type = fields.Selection(
        selection=[
            ('black', 'Lista Negra (Prohibido)'),
            ('white', 'Lista Blanca (Permitido)')
        ],
        string="Tipo",
        required=True
    )
    active = fields.Boolean(string="Activa", default=True)
    software_ids = fields.Many2many(
        'it.asset.software',
        relation='hw_list_software_rel',
        column1='list_id',
        column2='software_id',
        string="Software",
        help="Software en esta lista"
    )
    
    # Campos computados para estadísticas
    software_count = fields.Integer(
        string="Cantidad de Software",
        compute='_compute_software_count'
    )
    
    @api.depends('software_ids')
    def _compute_software_count(self):
        for record in self:
            record.software_count = len(record.software_ids)
    
    _sql_constraints = [
        ('unique_list_name', 'UNIQUE(name)', '¡Ya existe una lista con este nombre!'),
    ]
    
    def write(self, vals):
        """Override write para validar conflictos al activar listas y al añadir software"""
        # Si se está intentando activar una lista
        if vals.get('active') == True:
            for record in self:
                if not record.active:  # Solo validar si la lista estaba inactiva
                    self._validate_activation_conflicts(record)
        
        # Si se están modificando los software de una lista activa
        if 'software_ids' in vals:
            for record in self:
                if record.active and vals.get('active') == False: # Si la lista estaba activa y se desactivo no revisar  
                    continue
                elif record.active:  # Solo validar si la lista está activa 
                    self._validate_software_addition_conflicts(record, vals['software_ids'])
                elif vals.get('active') == True: # o se cambio a activa
                    # Calcular el estado final de software_ids después de aplicar los comandos
                    final_software_ids = self._calculate_final_software_ids(record, vals['software_ids'])
                    self._validate_activation_with_final_software(record, final_software_ids)
        
        return super().write(vals)
    
    def action_view_software(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Software en Lista',
            'res_model': 'it.asset.software',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.software_ids.ids)],
            'context': {
                'default_hw_list_ids': [(4, self.id)],
                'search_default_in_list': True
            }
        }
    
    def _calculate_final_software_ids(self, record, software_commands):
        """Calcula cuáles serían los IDs finales de software después de aplicar los comandos"""
        current_ids = set(record.software_ids.ids)
        
        for command in software_commands:
            if isinstance(command, (list, tuple)) and len(command) >= 1:
                cmd = command[0]
                
                if cmd == 0:  # (0, 0, values) - crear nuevo (no aplicable aquí)
                    continue
                elif cmd == 1:  # (1, id, values) - actualizar existente
                    continue
                elif cmd == 2:  # (2, id) - eliminar registro completamente
                    if len(command) >= 2:
                        current_ids.discard(command[1])
                elif cmd == 3:  # (3, id) - desvincular
                    if len(command) >= 2:
                        current_ids.discard(command[1])
                elif cmd == 4:  # (4, id) - vincular existente
                    if len(command) >= 2:
                        current_ids.add(command[1])
                elif cmd == 5:  # (5,) - desvincular todos
                    current_ids.clear()
                elif cmd == 6:  # (6, 0, [ids]) - reemplazar todos
                    if len(command) >= 3:
                        current_ids = set(command[2])
        
        return list(current_ids)
    
    def _validate_activation_with_final_software(self, record, final_software_ids):
        """Valida conflictos al activar una lista considerando el estado final de software"""
        if not final_software_ids:
            return  # No hay software en la lista final, no hay conflictos posibles
        
        # Determinar el tipo opuesto
        opposite_type = 'white' if record.type == 'black' else 'black'
        opposite_type_name = "negras" if record.type == "white" else "blancas"
        
        # Buscar listas activas del tipo opuesto
        opposite_lists = self.search([
            ('type', '=', opposite_type),
            ('active', '=', True),
            ('id', '!=', record.id)
        ])
        
        if not opposite_lists:
            return  # No hay listas del tipo opuesto activas
        
        # Obtener los software finales
        final_software = self.env['it.asset.software'].browse(final_software_ids)
        
        # Verificar conflictos para cada software final
        conflicting_software = []
        conflicting_lists_per_software = {}
        
        for software in final_software:
            if not software.exists():
                continue
                
            # Buscar en qué listas del tipo opuesto está este software
            lists_with_software = []
            for opposite_list in opposite_lists:
                if software in opposite_list.software_ids:
                    lists_with_software.append(opposite_list)
            
            if lists_with_software:
                conflicting_software.append(software)
                conflicting_lists_per_software[software.name] = [lst.name for lst in lists_with_software]
        
        # Si hay conflictos, lanzar excepción
        if conflicting_software:
            list_type_name = "lista blanca" if record.type == "white" else "lista negra"
            
            if len(conflicting_software) == 1:
                # Un solo software en conflicto
                software = conflicting_software[0]
                list_names = conflicting_lists_per_software[software.name]
                error_message = (
                    f"No se puede activar la {list_type_name} '{record.name}' porque "
                    f"el software '{software.name}' se encuentra en las listas {opposite_type_name} activas: "
                    f"[{', '.join(list_names)}]"
                )
            else:
                # Múltiples software en conflicto
                software_details = []
                for software in conflicting_software:
                    list_names = conflicting_lists_per_software[software.name]
                    software_details.append(f"'{software.name}' (en: {', '.join(list_names)})")
                
                error_message = (
                    f"No se puede activar la {list_type_name} '{record.name}' porque "
                    f"los siguientes software se encuentran en listas {opposite_type_name} activas:\n\n"
                    f"{chr(10).join(['• ' + detail for detail in software_details])}"
                )
            
            raise exceptions.ValidationError(error_message)
    
    def _validate_activation_conflicts(self, record):
        """Valida que no haya conflictos de software al activar una lista"""
        if not record.software_ids:
            return  # No hay software en la lista, no hay conflictos posibles
        
        # Determinar el tipo opuesto
        opposite_type = 'white' if record.type == 'black' else 'black'
        
        # Buscar listas activas del tipo opuesto
        opposite_lists = self.search([
            ('type', '=', opposite_type),
            ('active', '=', True),
            ('id', '!=', record.id)
        ])
        
        if not opposite_lists:
            return  # No hay listas del tipo opuesto activas
        
        # Encontrar software en común
        conflicting_software = []
        conflicting_lists = []
        
        for opposite_list in opposite_lists:
            common_software = record.software_ids & opposite_list.software_ids
            if common_software:
                conflicting_software.extend(common_software)
                conflicting_lists.append(opposite_list)
        
        # Si hay conflictos, lanzar excepción con mensaje detallado
        if conflicting_software:
            # Remover duplicados manteniendo el orden
            unique_software = []
            seen_ids = set()
            for software in conflicting_software:
                if software.id not in seen_ids:
                    unique_software.append(software)
                    seen_ids.add(software.id)
            
            software_names = [sw.name for sw in unique_software]
            list_names = [lst.name for lst in conflicting_lists]
            
            list_type_name = "lista blanca" if record.type == "white" else "lista negra"
            opposite_type_name = "listas negras" if record.type == "white" else "listas blancas"
            
            error_message = (
                f"No se puede activar la {list_type_name} '{record.name}' porque "
                f"el/los software(s) [{', '.join(software_names)}] se encontraron "
                f"en la/las {opposite_type_name} activa(s): [{', '.join(list_names)}].\n\n"
                f"Para activar esta lista, primero debe:\n"
                f"1. Desactivar las {opposite_type_name} mencionadas, o\n"
                f"2. Remover el/los software(s) conflictivos de una de las listas"
            )
            
            raise exceptions.ValidationError(error_message)
    
    def _validate_software_addition_conflicts(self, record, software_commands):
        """Valida que no se añada software que esté en listas del tipo opuesto activas"""
        if not software_commands:
            return
        
        # Determinar el tipo opuesto
        opposite_type = 'white' if record.type == 'black' else 'black'
        opposite_type_name = "negras" if record.type == "white" else "blancas"
        
        # Buscar listas activas del tipo opuesto
        opposite_lists = self.search([
            ('type', '=', opposite_type),
            ('active', '=', True),
            ('id', '!=', record.id)
        ])
        
        if not opposite_lists:
            return  # No hay listas del tipo opuesto activas
        
        # Extraer IDs de software que se están intentando añadir
        software_ids_to_add = []
        
        for command in software_commands:
            if isinstance(command, (list, tuple)) and len(command) >= 2:
                # Comando (4, id) - añadir software existente
                if command[0] == 4:
                    software_ids_to_add.append(command[1])
                # Comando (6, 0, [ids]) - reemplazar todos los software
                elif command[0] == 6 and len(command) >= 3:
                    current_software_ids = set(record.software_ids.ids)
                    new_software_ids = set(command[2])
                    # Solo los IDs que se están añadiendo (no los que ya estaban)
                    adding_ids = new_software_ids - current_software_ids
                    software_ids_to_add.extend(adding_ids)
        
        if not software_ids_to_add:
            return  # No se están añadiendo software nuevos
        
        # Verificar conflictos para cada software que se intenta añadir
        conflicting_software = []
        conflicting_lists_per_software = {}
        
        for software_id in software_ids_to_add:
            software = self.env['it.asset.software'].browse(software_id)
            if not software.exists():
                continue
                
            # Buscar en qué listas del tipo opuesto está este software
            lists_with_software = []
            for opposite_list in opposite_lists:
                if software in opposite_list.software_ids:
                    lists_with_software.append(opposite_list)
            
            if lists_with_software:
                conflicting_software.append(software)
                conflicting_lists_per_software[software.name] = [lst.name for lst in lists_with_software]
        
        # Si hay conflictos, lanzar excepción
        if conflicting_software:
            if len(conflicting_software) == 1:
                # Un solo software en conflicto
                software = conflicting_software[0]
                list_names = conflicting_lists_per_software[software.name]
                error_message = (
                    f"El software '{software.name}' no se puede añadir a la lista '{record.name}' "
                    f"porque se encuentra en las listas {opposite_type_name} activas: "
                    f"[{', '.join(list_names)}]"
                )
            else:
                # Múltiples software en conflicto
                software_details = []
                for software in conflicting_software:
                    list_names = conflicting_lists_per_software[software.name]
                    software_details.append(f"'{software.name}' (en: {', '.join(list_names)})")
                
                error_message = (
                    f"Los siguientes software no se pueden añadir a la lista '{record.name}' "
                    f"porque se encuentran en listas {opposite_type_name} activas:\n\n"
                    f"{chr(10).join(['• ' + detail for detail in software_details])}"
                )
            
            raise exceptions.ValidationError(error_message)
    
    # ... resto de métodos sin cambios ...
    
    def action_check_compliance(self):
        """Botón para verificar compliance de todo el software existente (sin hardware)"""
        try:
            # Verificar compliance de todo el software
            software_records = self.env['it.asset.software'].search([])
            incidents_created = 0
            
            for software in software_records:
                old_count = self.env['it.incident'].search_count([]) if 'it.incident' in self.env else 0
                self.check_software_compliance(software.id, hardware_id=None)
                if 'it.incident' in self.env:
                    new_count = self.env['it.incident'].search_count([])
                    incidents_created += (new_count - old_count)
            
            # Mostrar notificación
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Verificación Completada',
                    'message': f'Verificación de compliance completada. Se crearon {incidents_created} nuevos incidentes.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f"Error al verificar compliance: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Error al verificar compliance. Revise los logs para más detalles.',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_view_related_incidents(self):
        """Muestra incidentes relacionados con esta lista"""
        # Verificar si el modelo de incidentes está instalado
        if 'it.incident' not in self.env:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Función no disponible',
                    'message': 'El módulo de incidentes no está instalado',
                    'type': 'warning',
                    'sticky': True,
                }
            }
        
        # Buscar incidentes que mencionen software de esta lista
        software_names = self.software_ids.mapped('name')
        domain = []
        
        if software_names:
            for software_name in software_names:
                domain.append(('title', 'ilike', software_name))
            
            # Usar OR entre las condiciones
            if len(domain) > 1:
                domain = ['|'] * (len(domain) - 1) + domain
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Incidentes - {self.name}',
            'res_model': 'it.incident',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'search_default_group_by_severity': 1}
        }
    
    def action_force_activate(self):
        """Acción para forzar la activación de una lista (para casos especiales)"""
        for record in self:
            if not record.active:
                # Activar sin validaciones
                super(HWList, record).write({'active': True})
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Lista Activada Forzosamente',
                        'message': f'La lista "{record.name}" ha sido activada sin validaciones de conflicto.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
    
    def action_check_conflicts(self):
        """Acción para verificar conflictos potenciales sin activar la lista"""
        for record in self:
            try:
                self._validate_activation_conflicts(record)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Sin Conflictos',
                        'message': f'La lista "{record.name}" no tiene conflictos y puede ser activada.',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            except exceptions.ValidationError as e:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Conflictos Detectados',
                        'message': str(e),
                        'type': 'warning',
                        'sticky': True,
                    }
                }
    
    def action_force_add_software(self):
        """Acción para forzar la adición de software sin validaciones (para casos especiales)"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Función Administrativa',
                'message': 'Para forzar la adición de software, use el modo desarrollador y modifique directamente la base de datos.',
                'type': 'info',
                'sticky': False,
            }
        }
    
    @api.model
    def check_software_compliance(self, software_id, hardware_id=None):
        """
        Verifica si un software cumple con las políticas de listas activas
        y genera incidentes si es necesario.
        """
        # Verificar si el modelo de incidentes está instalado
        if 'it.incident' not in self.env:
            _logger.warning("Módulo de incidentes no instalado. No se crearán incidentes.")
            return
            
        software = self.env['it.asset.software'].browse(software_id)
        if not software.exists():
            return
            
        # Obtener listas activas
        active_black_lists = self.search([('type', '=', 'black'), ('active', '=', True)])
        active_white_lists = self.search([('type', '=', 'white'), ('active', '=', True)])
        
        # Verificar listas negras (prioridad alta)
        for black_list in active_black_lists:
            if software in black_list.software_ids:
                self._create_blacklist_incident(software, hardware_id, black_list)
                return  # Si está en lista negra, no verificar más
        
        # Si hay listas blancas activas, verificar que el software esté permitido
        if active_white_lists:
            is_in_whitelist = any(software in white_list.software_ids for white_list in active_white_lists)
            if not is_in_whitelist:
                self._create_whitelist_incident(software, hardware_id, active_white_lists)
    
    def _create_blacklist_incident(self, software, hardware_id, black_list):
        """Crea un incidente de alta severidad por software prohibido"""
        hardware_ref = None
        hardware_name = "No especificado"
        
        # Si se proporciona hardware_id y el modelo de hardware está instalado, usarlo
        if hardware_id and 'it.asset.hardware' in self.env:
            hardware = self.env['it.asset.hardware'].browse(hardware_id)
            if hardware.exists():
                hardware_ref = f"it.asset.hardware,{hardware_id}"
                hardware_name = hardware.name
        
        title = f"Software Prohibido Detectado: {software.name}"
        description = f"""
Se ha detectado software prohibido en el sistema:

Software: {software.name} (v{software.version})
Lista Negra: {black_list.name}
Hardware: {hardware_name}

ACCIÓN REQUERIDA: Remover inmediatamente este software del sistema.
        """
        
        # Verificar si ya existe un incidente similar reciente (últimas 24 horas)
        existing_incident = self.env['it.incident'].search([
            ('title', '=', title),
            ('detection_date', '>=', fields.Datetime.now() - datetime.timedelta(hours=24))
        ], limit=1)
        
        if not existing_incident:
            self.env['it.incident'].create({
                'title': title,
                'description': description,
                'severity': 'high',
                'asset_ref': hardware_ref,
            })
            _logger.warning(f"Incidente creado: Software prohibido {software.name} detectado")
    
    def _create_whitelist_incident(self, software, hardware_id, white_lists):
        """Crea un incidente de severidad media por software no autorizado"""
        hardware_ref = None
        hardware_name = "No especificado"
        
        if hardware_id and 'it.asset.hardware' in self.env:
            hardware = self.env['it.asset.hardware'].browse(hardware_id)
            if hardware.exists():
                hardware_ref = f"it.asset.hardware,{hardware_id}"
                hardware_name = hardware.name
        
        white_list_names = ', '.join(white_lists.mapped('name'))
        title = f"Software No Autorizado: {software.name}"
        description = f"""
Se ha detectado software que no está en las listas blancas activas:

Software: {software.name} (v{software.version})
Listas Blancas Activas: {white_list_names}
Hardware: {hardware_name}

ACCIÓN RECOMENDADA: Verificar si este software debe ser autorizado o removido.
        """
        
        # Verificar si ya existe un incidente similar reciente (últimas 24 horas)
        existing_incident = self.env['it.incident'].search([
            ('title', '=', title),
            ('detection_date', '>=', fields.Datetime.now() - datetime.timedelta(hours=24))
        ], limit=1)
        
        if not existing_incident:
            self.env['it.incident'].create({
                'title': title,
                'description': description,
                'severity': 'medium',
                'asset_ref': hardware_ref,
            })
            _logger.info(f"Incidente creado: Software no autorizado {software.name} detectado")
    
    @api.model
    def get_software_status(self, software_id):
        """
        Retorna el estado de un software según las listas activas:
        - 'prohibited': Está en lista negra
        - 'authorized': Está en lista blanca
        - 'gray': No está en ninguna lista (zona gris)
        """
        software = self.env['it.asset.software'].browse(software_id)
        if not software.exists():
            return 'gray'
            
        # Verificar listas negras
        active_black_lists = self.search([('type', '=', 'black'), ('active', '=', True)])
        for black_list in active_black_lists:
            if software in black_list.software_ids:
                return 'prohibited'
        
        # Verificar listas blancas
        active_white_lists = self.search([('type', '=', 'white'), ('active', '=', True)])
        for white_list in active_white_lists:
            if software in white_list.software_ids:
                return 'authorized'
        
        return 'gray'