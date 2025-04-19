# -*- coding: utf-8 -*-
# from odoo import http


# class LicenciaSsi(http.Controller):
#     @http.route('/licencia_ssi/licencia_ssi', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/licencia_ssi/licencia_ssi/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('licencia_ssi.listing', {
#             'root': '/licencia_ssi/licencia_ssi',
#             'objects': http.request.env['licencia_ssi.licencia_ssi'].search([]),
#         })

#     @http.route('/licencia_ssi/licencia_ssi/objects/<model("licencia_ssi.licencia_ssi"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('licencia_ssi.object', {
#             'object': obj
#         })

