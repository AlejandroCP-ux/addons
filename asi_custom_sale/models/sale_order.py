from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    project_responsible = fields.Many2one('res.users', string='Responsable del Proyecto')

    customer_signer_id = fields.Many2one(
        'res.partner',
        string="Firmante del Cliente",
        domain="[('can_sign_invoices', '=', True), ('parent_id', '=', partner_id)]",
        help="Persona autorizada para firmar facturas por parte del cliente.")
    responsible_employee = fields.Many2one('res.users', string='Firmado por:', default=lambda self: self.env.user.sale_team_id.user_id.parent_id)


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            return {
                'domain': {
                    'customer_signer_id': [
                        ('can_sign_invoices', '=', True),
                        ('parent_id', '=', self.partner_id.id)
                    ]
                }
            }
        else:
            return False


