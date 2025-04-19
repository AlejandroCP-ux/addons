# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2022-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from odoo import api, models, fields
from odoo.exceptions import UserError


class AccountMove(models.Model):
    """Inherited sale order model"""
    _inherit = "account.move"

    is_subscription = fields.Boolean(string='Is Subscription', default=False)
    subscription_ids = fields.Many2many('subscription.package', string='Subscriptions')
    subscriptions_count = fields.Integer(string='Subscriptions',
                                        compute='_compute_subscriptions_count')

    def _compute_subscriptions_count(self):
        for record in self:
          record.subscriptions_count = len(record.subscription_ids)

    def button_subscriptions(self):
        return {
            'name': 'Subscription',
            'sale_order': False,
            'domain': [('id', '=', self.subscription_ids.ids)],
            'view_type': 'form',
            'res_model': 'subscription.package',
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
            'context': {
                "create": False
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """ It displays subscription in account move """
        for rec in vals_list:
            if not 'subscription_ids' in rec:            
                so_id = self.env['sale.order'].search(
                    [('name', '=', rec.get('invoice_origin'))])
                if so_id.is_subscription is True:
                    new_vals_list = [{'is_subscription': True,
                                      'subscription_ids': [Command.set([so_id.subscription_id.id])]}]
                    vals_list[0].update(new_vals_list[0])
        return super().create(vals_list)


class Product(models.Model):
    """Inherited product template model"""
    _inherit = "product.template"

    is_subscription = fields.Boolean(string='Is Subscription', default=False)
    subscription_plan_id = fields.Many2one('subscription.package.plan',
                                           string='Subscription Plan')
