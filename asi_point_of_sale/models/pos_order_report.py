# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class PosOrderReport(models.Model):
    _inherit = "report.pos.order"

    # Eliminamos estos campos ya que no podemos acceder directamente a standard_price en la consulta SQL
    # product_cost = fields.Float(string='Coste', readonly=True)
    # cost_subtotal = fields.Float(string='Coste x Cantidad', readonly=True)
    # profit = fields.Float(string='Ganancia', readonly=True)

    # No sobrescribimos el método _select() para evitar problemas con la consulta SQL
