# -*- coding: utf-8 -*-
# from odoo import http


# class SgichsCore(http.Controller):
#     @http.route('/sgichs_core/sgichs_core', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sgichs_core/sgichs_core/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sgichs_core.listing', {
#             'root': '/sgichs_core/sgichs_core',
#             'objects': http.request.env['sgichs_core.sgichs_core'].search([]),
#         })

#     @http.route('/sgichs_core/sgichs_core/objects/<model("sgichs_core.sgichs_core"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sgichs_core.object', {
#             'object': obj
#         })
