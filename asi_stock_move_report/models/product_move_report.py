# -*- coding: utf-8 -*-

from odoo import api, fields, models
from collections import defaultdict

class ProductMoveReport(models.AbstractModel):
    _name = 'report.asi_stock_move_report.product_move_report_template'
    _description = 'Reporte de Movimientos por Producto'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            data = {}
        
        date_start = data.get('date_start')
        date_end = data.get('date_end')
        product_id = data.get('product_id')
        
        # Obtener el producto seleccionado
        product = self.env['product.product'].browse(product_id)
        
        # Obtener todos los movimientos del producto en el rango de fechas
        domain = [
            ('date', '>=', date_start),
            ('date', '<=', date_end),
            ('state', '=', 'done'),
            ('product_id', '=', product_id),
        ]
        
        moves = self.env['stock.move'].search(domain, order='date asc')
        
        # Preparar datos de movimientos
        moves_data = []
        running_stock = self._get_stock_quantity_at_date(product, date_start)
        
        # Contadores detallados para el resumen
        totals = {
            'entradas_recepcion': 0.0,
            'entradas_ajuste': 0.0,
            'entradas_transferencia': 0.0,
            'entradas_devolucion': 0.0,
            'salidas_venta': 0.0,
            'salidas_transferencia': 0.0,
            'salidas_ajuste': 0.0,
            'salidas_consumo': 0.0,
        }
        
        for move in moves:
            move_type = self._classify_move_detailed(move)
            quantity = move.product_uom_qty
            
            # Determinar si es entrada o salida y actualizar stock
            if move_type in ['entrada_recepcion', 'entrada_ajuste', 'entrada_transferencia', 'entrada_devolucion']:
                movement_direction = 'Entrada'
                running_stock += quantity
                totals[move_type.replace('entrada_', 'entradas_')] += quantity
            else:
                movement_direction = 'Salida'
                running_stock -= quantity
                totals[move_type.replace('salida_', 'salidas_')] += quantity
            
            # Obtener cantidad a mano antes del movimiento
            cantidad_antes = running_stock - quantity if movement_direction == 'Entrada' else running_stock + quantity
            
            moves_data.append({
                'date': move.date,
                'cantidad_antes': cantidad_antes,
                'cantidad_movida': quantity,
                'movement_direction': movement_direction,
                'move_type_display': self._get_move_type_display(move_type),
                'existencia_final': running_stock,
                'reference': move.reference or move.name or '',
            })
        
        return {
            'doc_ids': [1],
            'doc_model': 'product.move.report.wizard',
            'docs': [self.env['product.move.report.wizard'].browse(1)],
            'date_start': date_start,
            'date_end': date_end,
            'product': product,
            'moves_data': moves_data,
            'total_movements': len(moves),
            'totals': totals,
            'company': self.env.company,
        }
    
    def _classify_move_detailed(self, move):
        """
        Clasifica un movimiento según su tipo detallado
        """
        location_src = move.location_id
        location_dest = move.location_dest_id
        
        # ENTRADAS
        if location_dest.usage == 'internal':
            # Entrada por recepción (de proveedor)
            if location_src.usage == 'supplier':
                return 'entrada_recepcion'
            
            # Entrada por ajuste de inventario
            elif location_src.usage == 'inventory':
                return 'entrada_ajuste'
            
            # Entrada por transferencia interna (de otra ubicación interna)
            elif location_src.usage == 'internal':
                return 'entrada_transferencia'
            
            # Entrada por devolución (de cliente o producción)
            elif location_src.usage in ['customer', 'production']:
                return 'entrada_devolucion'
            
            # Otras entradas (transit, etc.)
            else:
                return 'entrada_recepcion'
        
        # SALIDAS
        elif location_src.usage == 'internal':
            # Salida por venta (a cliente)
            if location_dest.usage == 'customer':
                return 'salida_venta'
            
            # Salida por ajuste de inventario
            elif location_dest.usage == 'inventory':
                return 'salida_ajuste'
            
            # Salida por transferencia interna (a otra ubicación interna)
            elif location_dest.usage == 'internal':
                return 'salida_transferencia'
            
            # Salida por consumo (a producción)
            elif location_dest.usage == 'production':
                return 'salida_consumo'
            
            # Otras salidas (supplier, transit, etc.)
            else:
                return 'salida_transferencia'
        
        # Por defecto
        return 'entrada_recepcion'
    
    def _get_move_type_display(self, move_type):
        """
        Retorna el nombre para mostrar del tipo de movimiento
        """
        type_mapping = {
            'entrada_recepcion': 'Recepción',
            'entrada_ajuste': 'Ajuste',
            'entrada_transferencia': 'Transferencia Interna',
            'entrada_devolucion': 'Devolución',
            'salida_venta': 'Venta',
            'salida_transferencia': 'Transferencia Interna',
            'salida_ajuste': 'Ajuste',
            'salida_consumo': 'Consumo',
        }
        return type_mapping.get(move_type, 'Recepción')
    
    def _get_stock_quantity_at_date(self, product, date):
        """
        Obtiene la cantidad en stock de un producto en una fecha específica
        """
        # Buscar todos los movimientos del producto hasta la fecha
        moves = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('date', '<', date),
            ('state', '=', 'done'),
        ])
        
        quantity = 0.0
        for move in moves:
            if move.location_dest_id.usage == 'internal':
                quantity += move.product_uom_qty
            elif move.location_id.usage == 'internal':
                quantity -= move.product_uom_qty
        
        return quantity
