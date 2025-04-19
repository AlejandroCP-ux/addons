# -*- coding: utf-8 -*-
import requests
import odoo
from odoo.addons.website.controllers.main import WebsiteBinary
from odoo import http

class FixBinary(WebsiteBinary):

    @http.route(['/css/font/google'], type='http', auth="public")
    def load_google_font(self, **kw):
        res = requests.get("https://fonts.googleapis.com/css", params=kw)
        text = res.text.replace("https://fonts.gstatic.com", "/css/font/gstatic")
        response = http.Response(text, res.status_code, mimetype='text/css')
        return response

    @http.route(['/css/font/gstatic/<string:pre>/<string:family>/<string:version>/<string:font>/'], type='http', auth="public")
    def load_gstatic(self, pre, family, version, font, **kw):
        res = requests.get("https://fonts.gstatic.com/%s/%s/%s/%s" % (pre, family, version, font), params=kw)
        return http.Response(res.content, res.status_code, mimetype='font/ttf')

