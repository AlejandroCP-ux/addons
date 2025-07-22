# -*- coding: utf-8 -*-
from odoo import models, fields, api

class Incident(models.Model):
    _name = 'it.incident'
    _description = 'Incidente de TI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'detection_date desc'

    title = fields.Char(string='Título', required=True, tracking=True)
    description = fields.Text(string='Descripción Detallada')
    severity = fields.Selection(
        selection=[
            ('info', 'Informativo'),
            ('low', 'Baja'),
            ('medium', 'Media'),
            ('high', 'Alta')
        ],
        string='Severidad',
        default='medium',
        tracking=True
    )
    status = fields.Selection(
        [('new', 'Nuevo'),
         ('in_progress', 'En Progreso'),
         ('resolved', 'Resuelto'),
         ('closed', 'Cerrado')],
        default='new',
        string="Estado",
        tracking=True
    )
    detection_date = fields.Datetime(
        string='Fecha de Detección',
        default=fields.Datetime.now,
        readonly=True
    )

    asset_ref = fields.Reference(
        selection=lambda self: self._get_asset_models(),
        string='Activo Relacionado',
        ondelete='set null'
    )

    @api.model
    def _get_asset_models(self):
        """
        Retorna una lista de tuplas con los modelos que heredan de 'it.asset'.
        Esto permite que los módulos extensores registren sus modelos de activos
        sin crear una dependencia directa en el módulo de incidentes.
        """
        # CORRECCIÓN: El método original causaba un error porque el modelo 'ir.model'
        # no tiene un campo 'inherits' que se pueda buscar directamente.
        # La forma correcta y robusta es iterar a través del registro de modelos
        # de Odoo y verificar el atributo _inherit de cada clase de modelo.
        selection = []
        # Iteramos sobre todos los modelos cargados en el registro de Odoo.
        for model_name in self.env:
            # Obtenemos la clase del modelo para inspeccionar sus atributos.
            model_cls = self.env.get(model_name)
            if not model_cls:
                continue

            # Verificamos si el modelo tiene el atributo _inherit y si 'it.asset'
            # está en la lista de modelos heredados.
            # Nos aseguramos de que _inherit no sea None y sea una lista/tupla.
            inherits = getattr(model_cls, '_inherit', [])
            if not inherits:
                continue
            
            # El atributo _inherit puede ser un string o una lista/tupla. Lo normalizamos a lista.
            if isinstance(inherits, str):
                inherits = [inherits]
            
            if 'it.asset' in inherits:
                # Si hereda de it.asset, lo buscamos en ir.model para obtener
                # su nombre legible para el usuario (el campo 'name').
                model_record = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
                if model_record:
                    selection.append((model_record.model, model_record.name))

        # Si por alguna razón no se encuentra nada (por ejemplo, durante la instalación inicial),
        # devolvemos una opción por defecto para evitar que el campo falle completamente.
        if not selection:
             return [('it.asset', 'Activo de TI')]
             
        return selection