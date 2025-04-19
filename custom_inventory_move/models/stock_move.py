from odoo import models, fields, api
from datetime import datetime

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    remaining_qty = fields.Float(
        string='Cantidad Restante',
        compute='_compute_remaining_qty',
        store=True,
        help='Stock disponible después de este movimiento.'
    )

    @api.depends('product_id', 'date', 'state', 'qty_done', 'location_id', 'location_dest_id')
    def _compute_remaining_qty(self):
        internal_locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        for line in self:
            if line.state != 'done' or not line.product_id:
                line.remaining_qty = 0.0
                continue
            
            # Determinar si el movimiento afecta el stock global
            from_internal = line.location_id in internal_locations
            to_internal = line.location_dest_id in internal_locations
            is_incoming = to_internal and not from_internal  # Entrada a stock
            is_outgoing = from_internal and not to_internal  # Salida de stock

            if not (is_incoming or is_outgoing):
                line.remaining_qty = 0.0
                continue

            # Calcular la fecha como datetime al final del día
            date_end = datetime.combine(line.date, datetime.max.time())
            
            # Obtener el stock disponible hasta esta fecha en ubicaciones internas
            product = line.product_id.with_context(
                to_date=date_end,
                location=internal_locations.ids
            )
            line.remaining_qty = product.qty_available