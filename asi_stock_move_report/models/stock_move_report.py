# -*- coding: utf-8 -*-

from odoo import api, fields, models
from collections import defaultdict

class StockMoveReport(models.AbstractModel):
    _name = 'report.asi_stock_move_report.stock_move_report_template'
    _description = 'Reporte de Movimientos de Inventario'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            data = {}
        
        date_start = data.get('date_start')
        date_end = data.get('date_end')
        warehouse_id = data.get('warehouse_id')
        
        # Obtener ubicaciones del almacén seleccionado
        warehouse = self.env['stock.warehouse'].browse(warehouse_id) if warehouse_id else None
        warehouse_locations = self.env['stock.location']
        
        if warehouse:
            warehouse_locations = warehouse.lot_stock_id.child_ids | warehouse.lot_stock_id
        
        # Obtener todos los movimientos en el rango de fechas y almacén
        domain = [
            ('date', '>=', date_start),
            ('date', '<=', date_end),
            ('state', '=', 'done'),
            ('product_id', '!=', False),
        ]
        
        # Filtrar por ubicaciones del almacén si se especifica
        if warehouse_locations:
            domain.append('|')
            domain.append(('location_id', 'in', warehouse_locations.ids))
            domain.append(('location_dest_id', 'in', warehouse_locations.ids))
        
        moves = self.env['stock.move'].search(domain)
        
        # Diccionario para consolidar movimientos por producto
        product_moves = defaultdict(lambda: {
            'product_id': None,
            'product_code': '',
            'product_name': '',
            'product_uom': '',
            'cantidad_movimientos': 0,
            'cantidad_a_mano': 0.0,
            'entradas': 0.0,
            'ventas': 0.0,
            'otras_salidas': 0.0,
            'consumo': 0.0,
            'existencia_final': 0.0,
        })
        
        # Procesar cada movimiento
        for move in moves:
            product_id = move.product_id.id
            
            # Inicializar datos del producto si es la primera vez
            if product_moves[product_id]['product_id'] is None:
                product_moves[product_id]['product_id'] = product_id
                product_moves[product_id]['product_code'] = move.product_id.default_code or ''
                product_moves[product_id]['product_name'] = move.product_id.name or ''
                product_moves[product_id]['product_uom'] = move.product_uom.name or ''
                
                # Obtener cantidad a mano al inicio del período para el almacén específico
                product_moves[product_id]['cantidad_a_mano'] = self._get_stock_quantity_at_date(
                    move.product_id, date_start, warehouse_locations
                )
            
            # Incrementar contador de movimientos para este producto
            product_moves[product_id]['cantidad_movimientos'] += 1
            
            # Clasificar el movimiento según su tipo
            move_type = self._classify_move(move)
            quantity = move.product_uom_qty
            
            if move_type == 'entrada':
                product_moves[product_id]['entradas'] += quantity
            elif move_type == 'venta':
                product_moves[product_id]['ventas'] += quantity
            elif move_type == 'otra_salida':
                product_moves[product_id]['otras_salidas'] += quantity
            elif move_type == 'consumo':
                product_moves[product_id]['consumo'] += quantity
        
        # Calcular existencias finales
        for product_id in product_moves:
            product_data = product_moves[product_id]
            product_data['existencia_final'] = (
                product_data['cantidad_a_mano'] + 
                product_data['entradas'] - 
                product_data['ventas'] - 
                product_data['otras_salidas'] - 
                product_data['consumo']
            )
        
        # Convertir a lista y ordenar por nombre de producto
        products_data = list(product_moves.values())
        products_data.sort(key=lambda x: x['product_name'])
        
        # Filtrar solo productos que tuvieron movimientos
        products_with_movements = [p for p in products_data if 
                             p['entradas'] > 0 or p['ventas'] > 0 or 
                             p['otras_salidas'] > 0 or p['consumo'] > 0]
        
        return {
            'doc_ids': [1],  # Solo necesitamos un documento ficticio
            'doc_model': 'stock.move.report.wizard',
            'docs': [self.env['stock.move.report.wizard'].browse(1)],
            'date_start': date_start,
            'date_end': date_end,
            'warehouse': warehouse,
            'products_data': products_with_movements,
            'total_products_with_movements': len(products_with_movements),
            'total_movements': len(moves),  # Total de movimientos en el período
            'company': self.env.company,
        }
    
    def _classify_move(self, move):
        """
        Clasifica un movimiento según su tipo
        """
        location_src = move.location_id
        location_dest = move.location_dest_id
        
        # Entradas: de proveedor, inventario, producción a ubicación interna
        if (location_src.usage in ['supplier', 'inventory', 'production'] and 
            location_dest.usage == 'internal'):
            return 'entrada'
        
        # Ventas: de ubicación interna a cliente
        if (location_src.usage == 'internal' and 
            location_dest.usage == 'customer'):
            return 'venta'
        
        # Consumo: de ubicación interna a producción
        if (location_src.usage == 'internal' and 
            location_dest.usage == 'production'):
            return 'consumo'
        
        # Otras salidas: cualquier otra salida de ubicación interna
        if (location_src.usage == 'internal' and 
            location_dest.usage in ['inventory', 'supplier', 'transit']):
            return 'otra_salida'
        
        # Por defecto, considerar como entrada si va a ubicación interna
        if location_dest.usage == 'internal':
            return 'entrada'
        else:
            return 'otra_salida'
    
    def _get_stock_quantity_at_date(self, product, date, warehouse_locations=None):
        """
        Obtiene la cantidad en stock de un producto en una fecha específica para un almacén
        """
        domain = [
            ('product_id', '=', product.id),
            ('date', '<', date),
            ('state', '=', 'done'),
        ]
        
        # Filtrar por ubicaciones del almacén si se especifica
        if warehouse_locations:
            domain.append('|')
            domain.append(('location_id', 'in', warehouse_locations.ids))
            domain.append(('location_dest_id', 'in', warehouse_locations.ids))
        
        moves = self.env['stock.move'].search(domain)
        
        quantity = 0.0
        for move in moves:
            # Solo considerar movimientos que involucren las ubicaciones del almacén
            if warehouse_locations:
                if move.location_dest_id in warehouse_locations:
                    quantity += move.product_uom_qty
                elif move.location_id in warehouse_locations:
                    quantity -= move.product_uom_qty
            else:
                # Lógica original si no hay filtro de almacén
                if move.location_dest_id.usage == 'internal':
                    quantity += move.product_uom_qty
                elif move.location_id.usage == 'internal':
                    quantity -= move.product_uom_qty
        
        return quantity
