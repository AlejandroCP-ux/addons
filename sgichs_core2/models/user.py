from odoo import models, fields, api

class ITUser(models.Model):
    _name = 'it.user'
    _description = 'Usuario Autorizado de TI'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    user_id = fields.Many2one(
        'res.users',
        string='Usuario del Sistema',
        required=True,
        tracking=True,
        ondelete='cascade'
    )
    name = fields.Char(string='Nombre', related='user_id.name', store=True)
    authorization_date = fields.Date(
        string='Fecha de Autorización',
        default=fields.Date.context_today,
        tracking=True
    )
    status = fields.Selection(
        selection=[
            ('draft', 'Pendiente'),
            ('active', 'Activo'),
            ('revoked', 'Revocado')
        ],
        string='Estado de Autorización',
        default='draft',
        tracking=True
    )
    notes = fields.Text(string='Observaciones')

    # Relaciones opcionales (se completarán si los módulos están instalados)
    # comentado al dar error relacional
    # TODO: resolver el error relacional
    # hardware_ids = fields.One2many(
    #     'it.asset.hardware',
    #     'responsible_id',
    #     string='Hardware Asignado'
    # )
    software_ids = fields.Many2many(
        'it.asset.software',
        string='Software Autorizado'
    )

    # Restricción: 1 usuario del sistema = 1 usuario autorizado
    _sql_constraints = [
        ('unique_user', 
         'UNIQUE(user_id)', 
         'Cada usuario del sistema solo puede tener una autorización de TI')
    ]


    #=====================#
    #      FUNCIONES      #
    #=====================#  


    # Método para verificar dependencias
    def _module_installed(self, module_name):
        return self.env['ir.module.module'].search([
            ('name', '=', module_name),
            ('state', 'in', ['installed', 'to upgrade'])
        ], limit=1)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        # Notificar al crear nueva autorización
        record.message_post(
            body=f"Autorización creada para el usuario: {record.user_id.name}"
        )
        return record

    def action_activate(self):
        """Activa la autorización del usuario"""
        self.write({'status': 'active'})
        self.message_post(body="Autorización activada")

    def action_revoke(self):
        """Revoca la autorización del usuario"""
        self.write({'status': 'revoked'})
        # Desasociar hardware al revocar
        self.write({'hardware_ids': [(5, 0, 0)]})
        self.message_post(body="Autorización revocada")

    @api.model
    def sync_existing_users(self):
        """Crea registros de autorización para usuarios existentes"""
        existing_users = self.env['res.users'].search([])
        for user in existing_users:
            if not self.search([('user_id', '=', user.id)]):
                self.create({
                    'user_id': user.id,
                    'status': 'active' if user.active else 'revoked'
                })
        return True