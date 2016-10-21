# -*- coding: utf-8 -*-

from openerp import models, api, fields

class Model(models.Model):
    _name = 'hs.itm.model'
    _rec_name = 'display_name'
    model = fields.Char(string='Model',required=True)
    brand = fields.Char(string='Brand',translation=True,required=True)
    display_name = fields.Char(string='Name',compute='_display_name')

    @api.multi
    @api.depends('brand', 'model')
    def _display_name(self):
        self.ensure_one()
        if self.brand and self.model:
            self.display_name = '%s - %s' % self.brand, self.model

class Server(models.Model):
    _name = 'hs.itm.server'
    name = fields.Char(string='Tag',required=True)
    model = fields.Many2one(string='Model',required=)
    ip = fields.Char(string='IP Address')
    status = fields.Selection(string='Status',translation=True,selection=[
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('disabled', 'Disabled'),
        ('removed', 'Removed')
    ])
    logs = fields.One2many(string='Logs')
    description = fields.Text(string='Description')

class MaintenanceLog(models.Model):
    _name = 'hs.itm.server_maintenance_log'
    server = fields.Many2many(string='Server')
    time = fields.Datetime(string='Time')
    hours = fields.Float(string='Hours')
    remark = fields.Html(string='Remark')
