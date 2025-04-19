from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    bank_accounts = fields.Text(compute='_compute_bank_accounts', store=True)

    @api.depends('bank_ids','bank_ids.acc_holder_name','bank_ids.currency_id','bank_ids.acc_number')
    def _compute_bank_accounts(self):
        for partner in self:
            bank_accounts = []
            for bank in partner.bank_ids:
                bank_account = f"No: {bank.acc_number}, Bco: {bank.bank_id.name}, Titular: {bank.acc_holder_name} Moneda: {bank.currency_id.name}"
                bank_accounts.append(bank_account)
            partner.bank_accounts = ',- '.join(bank_accounts)