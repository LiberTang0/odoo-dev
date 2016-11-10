# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Material(models.Model):
    _name = 'hs.eas.material'
    _description = 'Material'
    _order = 'number'

    name = fields.Char('Name', required=True)
    base_unit = fields.Many2one('hs.eas.measure.unit', string='Base Unit', required=True)
    number = fields.Char('Code Number', required=True)
    price_precision = fields.Integer('Price Precision', required=True, default=2)
    version = fields.Integer('Version', required=True, default=1)
    status = fields.Selection([
    ('unapproved', 'Not Approved'),
    ('approved', 'Approved'),
    ('disabled', 'Disabled')
    ], string='Status', required=True, default='unapproved')
