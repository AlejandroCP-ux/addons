from odoo import fields, models


class ResUserRole(models.Model):
  _inherit = 'res.users.role'
  
  role_type = fields.Selection([
           ('tecnico', 'Tecnico'),
           ('direccion', 'Dirección'),
           ('obrero', 'Obrero')],
           string='Tipo de rol')

# class ResUsersRoleLine(models.Model):
#   _inherit = "res.users.role.line"

#   level_id = fields.Many2one('hr.skill.level', string="Nivel", required=False, help="Nivel")





  