from odoo import fields, models

class ResUsersRole(models.Model):
    _inherit = 'res.users.role'

    hidden_menu_access_ids = fields.Many2many(
        'ir.ui.menu',
        'ir_ui_role_hidden_menu_rel',
        'role_id',  # Cambiado de 'uid' a 'role_id'
        'menu_id',
        string='Hide Access Menu'
    )
