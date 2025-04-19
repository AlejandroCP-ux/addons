from odoo import models, fields

class HrSkillTypeCustom(models.Model):
    _inherit = 'hr.skill.type'

    #role_id = fields.Many2one('res.users.role', string="Rol", required=False, help="Rol")

    role_id = fields.Many2many('res.users.role', column1='skill_type_id', column2='role_id', string='Roles')


