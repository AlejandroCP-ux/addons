from odoo import fields, models, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    hide_menu_access_ids = fields.Many2many(
        'ir.ui.menu',
        'ir_ui_hide_menu_rel',
        'user_id',
        'menu_id',
        string='Hide Access Menu',
        compute='_compute_hide_menu_access_ids',
        store=True
    )

    @api.depends('role_ids.hidden_menu_access_ids', 'role_ids.hidden_menu_access_ids.name')
    def _compute_hide_menu_access_ids(self):
        for user in self:
            menu_ids = set()
            for role in user.role_ids:
                menu_ids.update(role.hidden_menu_access_ids.ids)
            user.hide_menu_access_ids = [(6, 0, list(menu_ids))]
            user.clear_caches()
