# -*- coding: utf-8 -*-
from odoo import http

# class HsEas(http.Controller):
#     @http.route('/hs_eas/hs_eas/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hs_eas/hs_eas/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('hs_eas.listing', {
#             'root': '/hs_eas/hs_eas',
#             'objects': http.request.env['hs_eas.hs_eas'].search([]),
#         })

#     @http.route('/hs_eas/hs_eas/objects/<model("hs_eas.hs_eas"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hs_eas.object', {
#             'object': obj
#         })