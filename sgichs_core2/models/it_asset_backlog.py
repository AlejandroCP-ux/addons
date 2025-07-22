# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ITAssetBacklog(models.Model):
    """
    Este modelo actúa como un área de preparación (staging area) para los activos
    que son descubiertos o importados antes de ser aprobados y convertidos
    en activos formales (hardware, software, etc.).
    """
    _name = 'it.asset.backlog'
    _description = 'Backlog de Activos de TI'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre Detectado', required=True, tracking=True)
    description = fields.Text(string='Descripción Adicional')

    # COMENTARIO: El tipo en el backlog es solo informativo. La lógica de transferencia
    # se basará en este campo para saber qué modelo de activo crear.
    type = fields.Selection(
        selection=[
            ('hardware', 'Hardware'),
            ('software', 'Software'),
            ('network', 'Red'),
            ('unknown', 'Desconocido'),
        ],
        string='Tipo Detectado',
        required=True,
        default='unknown',
        tracking=True
    )

    raw_data = fields.Text(string="Datos en Bruto", help="Datos originales del descubrimiento o importación, usualmente en formato JSON.")
    status = fields.Selection(
        [('pending', 'Pendiente de Aprobación'),
         ('processed', 'Procesado'),
         ('ignored', 'Ignorado')],
        default='pending',
        string="Estado"
    )

    def action_approve(self):
        """
        COMENTARIO: Esta es una función clave diseñada para ser extendida.
        El módulo core no sabe cómo crear un 'hardware' o 'software'.
        Los módulos 'sgich_hardware', 'sgich_software', etc., heredarán este
        modelo y sobreescribirán este método para manejar la creación de
        sus respectivos activos.

        Si un módulo no está instalado, su lógica de aprobación no se ejecutará.
        """
        self.ensure_one()
        if self.type not in ['hardware', 'software', 'network']:
             raise UserError(_("No se puede aprobar un activo de tipo '%s' desde el core. Se necesita el módulo correspondiente.") % self.type)

        # La lógica específica se implementará en los módulos de extensión.
        # Por ejemplo, en sgich_hardware:
        # if self.type == 'hardware':
        #     self.env['it.asset.hardware'].create(...)
        #     self.status = 'processed'
        # else:
        #     super(ITAssetBacklog, self).action_approve()

        raise NotImplementedError(_("La lógica de aprobación para el tipo '%s' no está implementada. Instale el módulo correspondiente (ej. sgich_hardware).") % self.type)

    def action_ignore(self):
        self.write({'status': 'ignored'})