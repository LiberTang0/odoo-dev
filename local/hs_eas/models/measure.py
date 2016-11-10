# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MeasureUnitGroup(models.Model):
    _name = 'hs.eas.measure.unit.group'
    _description = 'Measure Unit Group'
    _order = 'number'

    name = fields.Char('Name', required=True, translate=True)
    parent_id = fields.Many2one('hs.eas.measure.unit.group', string='Parent')
    number = fields.Char('Code Number', required=True)


class MeasureUnit(models.Model):
    _name = 'hs.eas.measure.unit'
    _description = 'Measure Unit'
    _order = 'number'

    name = fields.Char('Name', requried=True, translate=True)
    measure_group_id = fields.Many2one('hs.eas.measure.unit.group', string='Measure Group')
    number = fields.Char('Code Number', required=True)
    conversion_rate = fields.Float('Conversion Rate', required=True, default=1)
    is_base_unit = fields.Boolean('Is Base Unit?', required=True, default=False)
    precision = fields.Integer('Precision', required=True, default=2)
