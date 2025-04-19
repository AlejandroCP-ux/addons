from odoo import api, SUPERUSER_ID, models, fields


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


class Contract(models.Model):
    _inherit = 'hr.contract'
    
    role_ids = fields.Many2many('hr.contract.rolelevel', string='Roles')
    wage_movable = fields.Monetary('Salario movible',  tracking=True, help="Salario movible mensual")

    def write(self, vals):
        """ Automatically update role dates """
        write_res = super(Contract, self).write(vals)

        if self.employee_id.user_id.id != SUPERUSER_ID:
        
            role_lines= self.env['res.users.role.line'].search([('role_id','in',self.role_ids.mapped('role_id.id')),('user_id','=', self.employee_id.user_id.id)])
            all_roles = self.env['res.users.role'].search([('role_id','in',self.role_ids.mapped('role_id.id'))])
            pending_roles = all_roles - role_lines.role_id

            for line in role_lines:                
                line.update({
                'date_from': self.date_start,
                'date_to': self.date_end,
                }) 
            for record in self:
                for role in pending_roles:
                    res = self.env['res.users.role.line'].create({
                    'role_id': role.id,
                    'user_id': record.employee_id.user_id.id,
                    'date_from': record.date_start,
                    'date_to': record.date_end,
                }) 
        return write_res 
