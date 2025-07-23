from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_sgichs_software = fields.Boolean(string="Activar el control de software")
    module_sgichs_hardware = fields.Boolean(string="Activar el control de hardware")
    module_sgichs_red = fields.Boolean(string="Activar el control de dispositivos en la red")
    module_sgichs_users = fields.Boolean(string="Activar el control de usuarios")
