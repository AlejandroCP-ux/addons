# -*- coding: utf-8 -*-
# from odoo import http


# class CustomInventoryMove(http.Controller):
#     @http.route('/custom_inventory_move/custom_inventory_move', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom_inventory_move/custom_inventory_move/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom_inventory_move.listing', {
#             'root': '/custom_inventory_move/custom_inventory_move',
#             'objects': http.request.env['custom_inventory_move.custom_inventory_move'].search([]),
#         })

#     @http.route('/custom_inventory_move/custom_inventory_move/objects/<model("custom_inventory_move.custom_inventory_move"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom_inventory_move.object', {
#             'object': obj
#         })

