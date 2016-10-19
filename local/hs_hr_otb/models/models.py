# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime

def get_datetime(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

def get_time_diff_in_hour(start_time_str, end_time_str):
    secs = (get_datetime(end_time_str) - get_datetime(start_time_str)).total_seconds()
    return round((secs - 3600 if secs >= 5 * 3600 else secs)/1800.0, 0) * 0.5

def get_default_datetime():
    return datetime.combine(datetime.today(), datetime.min.time())

class BaseAttendanceRecord(models.AbstractModel):
    _name = 'hs_hr_otb.base_attendance_record'
    name = fields.Char(compute='_record_name',store=True)
    employee_id = fields.Many2one('res.partner',string='Employee')
    start_time = fields.Datetime(string='From',default=get_default_datetime())
    end_time = fields.Datetime(string='To',default=get_default_datetime())
    hours = fields.Float(compute='_period_in_hour',string='Hours',readonly=True,store=True)
    reason = fields.Char(string='Reason')
    # once a record is archived, it cannot be edited or deleted
    archived = fields.Boolean(string='Archived?',default=False)

    @api.multi
    @api.depends('employee_id', 'start_time')
    def _record_name(self):
        for record in self:
            if record.employee_id and record.start_time:
                record.name = record.employee_id.name + '-' + get_datetime(record.start_time).strftime('%Y%m%d_%H%M')

    @api.multi
    @api.depends('start_time', 'end_time')
    def _period_in_hour(self):
        for record in self:
            if record.start_time and record.end_time:
                # the unit for counting is 0.5 hour
                record.hours = get_time_diff_in_hour(record.start_time, record.end_time)
                print record.hours

    @api.constrains('start_time', 'end_time')
    def _check_time_period(self):
        for record in self:
            if get_datetime(record.start_time) >= get_datetime(record.end_time):
                raise Warning("End time must be later than start time!")

class OvertimeAndTimeOff(models.Model):
    _name = 'hs_hr_otb.otto'
    _inherit = ['hs_hr_otb.base_attendance_record']
    rec_type = fields.Selection(string="Type",required=True,selection=[
        ('paid', 'Paid Overtime'),
        ('unpaid', 'Unpaid Overtime'),
        ('timeoff', 'Take Time Off')
    ])

    @api.model
    def create(self, vals):
        print vals
        cr = self.env.cr
        cr.execute('SAVEPOINT create_otto_record')
        record = super(OvertimeAndTimeOff, self).create(vals)
        delta = 0.0
        if record.rec_type == 'unpaid':
            delta = record.hours
        elif record.rec_type == 'timeoff':
            delta = -1 * record.hours
        if delta != 0:
            Balance = self.env['hs_hr_otb.balance']
            balance = Balance.search([('employee_id','=',vals['employee_id'])])
            balance.ensure_one()
            if delta < 0 and balance.hours - delta < 0:
                cr.execute('ROLLBACK TO SAVEPOINT create_otto_record')
                raise Warning('There isn\'t enough time off balance left for this employee!')
            else:
                balance.hours += delta
        return record
    #
    # @api.multi
    # def write(self, vals):
    #     self.ensure_one()
    #     _check_balance_enough(self, vals)
    #     super(OvertimeAndTimeOff, self).update(vals)
    #     _update_balance(self, vals, )
    #     return True
    #
    # @api.multi
    # def unlink(self, vals):
    #     self.ensure_one()
    #

    def _check_balance_enough(self, vals):
        Balance = self.env['hs_hr_otb.balance']
        balance = Balance.search([('=','employee_id',self.employee_id.id)])
        balance.ensure_one()
        hours = get_time_diff_in_hour(vals.start_time, vals.end_time)
        if vals.rec_type == 'timeoff' and hours > balance.hours:
            raise Warning('There isn\'t enough time off balance left for this employee!')
        return True

    def _update_balance(self, vals, delta):
        Balance = self.env['hs_hr_otb.balance']
        balance = Balance.search([('employee_id','=',self.employee_id.id)])[0]
        balance.hours += delta
        return True

class Balance(models.Model):
    _name = 'hs_hr_otb.balance'
    name = fields.Char(compute='_record_name',string='Name',store=True)
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True)

    @api.depends('employee_id')
    def _record_name(self):
        self.ensure_one()
        if self.employee_id:
            self.name = self.employee_id.name + '-TimeOffBalance'

class Adjustment(models.Model):
    _name = 'hs_hr_otb.adjustment'
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True)
    reason = fields.Char(string='Reason',required=True)
