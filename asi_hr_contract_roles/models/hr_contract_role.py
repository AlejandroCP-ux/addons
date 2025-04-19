'''
Created on sept 23, 2023

@author: Javier
'''
from odoo import api, models, fields


class HrContractRoleLevel(models.Model):
  _name = 'hr.contract.rolelevel'
  _description = 'Contract Roles'
    

  name = fields.Char(compute='_compute_name', store=True)  
  role_id = fields.Many2one('res.users.role', string="Rol",
                              required=True, help="Rol")
  readiness_level = fields.Selection([('adiestrado','Adiestrado'),('avanzado','Avanzado'),('profesional','Profesional'),('experto','Experto'),('certificado','Certificado'),('no_certificado','No Certificado'),('sin_categoria','Sin Categoría')],
        string='Knowledge Level', required=True, help="Nivel")


  @api.depends('role_id','readiness_level')
  def _compute_name(self):
    for record in self:
      readiness_levels = dict(self._fields["readiness_level"]._description_selection(self.env))
      record.name = '%s - %s' %(record.role_id.name,readiness_levels[record.readiness_level]) if record.role_id and record.readiness_level else ''
      _sql_constraints = [('name_unique', 'unique(name)', 'Role Level should be unique!')]


  
  