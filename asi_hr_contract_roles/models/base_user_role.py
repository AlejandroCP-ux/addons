'''
Created on sept 23, 2023

@author: Javier
'''
from odoo import api, models, fields



class ResUserRole(models.Model):
  _inherits = 'res.users.role'
 

  level_id = fields.Many2one('hr.skill.level', string="Nivel",
                              required=True, help="Nivel")
  