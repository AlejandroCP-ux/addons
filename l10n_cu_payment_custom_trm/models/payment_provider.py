# -*- coding: utf-8 -*-

from odoo import _, models, fields, api
from odoo.tools import is_html_empty


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    custom_mode = fields.Selection(selection_add=[('transfermovil', "Transfermovil")], ondelete={'transfermovil': 'set wire_transfer'})
    
    def _transfer_ensure_pending_msg_is_set(self):
        super()._transfer_ensure_pending_msg_is_set()
        
        transfer_providers_without_msg = self.filtered(
            lambda p: p.code == 'custom'
            and p.custom_mode == 'transfermovil'
            and is_html_empty(p.pending_msg)
        )

        if not transfer_providers_without_msg:
            return  # Don't bother translating the messages.

        account_payment_module = self.env['ir.module.module']._get('account_payment')
        if account_payment_module.state != 'installed':
            transfer_providers_without_msg.pending_msg = f'<div>' \
                f'<h3>{_("Please use the following transfer details")}</h3>' \
                f'<h4>{_("Bank Account")}</h4>' \
                f'<h4>{_("Communication")}</h4>' \
                f'<p>{_("Please use the order name as communication reference.")}</p>' \
                f'</div>'
            return

        for provider in transfer_providers_without_msg:
            company_id = provider.company_id.id
            accounts = self.env['account.journal'].search([
                ('type', '=', 'bank'), ('company_id', '=', company_id)
            ]).bank_account_id
            provider.pending_msg = f'<div>' \
                f'<h3>{_("Please use the following transfer details")}</h3>' \
                f'<h4>{_("Bank Account") if len(accounts) == 1 else _("Bank Accounts")}</h4>' \
                f'<ul>{"".join(f"<li>{account.display_name}</li>" for account in accounts)}</ul>' \
                f'<h4>{_("Communication")}</h4>' \
                f'<p>{_("Please use the order name as communication reference.")}</p>' \
                f'</div>'
