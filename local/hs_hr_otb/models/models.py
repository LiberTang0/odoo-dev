# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime

def get_datetime(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

def get_time_diff_in_hour(start_time_str, end_time_str):
    secs = (get_datetime(end_time_str) - get_datetime(start_time_str)).total_seconds()
    return round((secs - 3600 if secs >= 5 * 3600 else secs)/1800.0, 0) * 0.5

class BaseAttendanceRecord(models.AbstractModel):
    _name = 'hs_hr_otb.base_attendance_record'
    name = fields.Char(compute='_record_name',store=True)
    employee_id = fields.Many2one('res.partner',string='Employee')
    # date = fields.Date(compute='_record_date',string='Date',store=True,readonly=True)
    start_time = fields.Datetime(string='From',default=datetime.combine(datetime.today(), datetime.min.time()))
    end_time = fields.Datetime(string='To',default=datetime.combine(datetime.today(), datetime.min.time()))
    hours = fields.Float(compute='_period_in_hour',string='Hours',readonly=True,store=True)
    reason = fields.Char(string='Reason')

    @api.multi
    @api.depends('employee_id', 'start_time')
    def _record_name(self):
        for record in self:
            if record.employee_id and record.start_time:
                record.name = record.employee_id.name + '-' + get_datetime(record.start_time).strftime('%Y%m%d_%H%M')

    # @api.depends('start_time')
    # @api.multi
    # def _record_date(self):
    #     for record in self:
    #         if record.start_time:
    #             record.date = get_datetime(record.start_time).date()

    @api.multi
    @api.depends('start_time', 'end_time')
    def _period_in_hour(self):
        for record in self:
            hours = 0
            if record.start_time and record.end_time:
                # 最小的时数单位为半个小时
                hours = get_time_diff_in_hour(record.start_time, record.end_time)
            record.period_in_hour = '%.1f' % hours

    @api.constrains('start_time', 'end_time')
    def _check_time_period(self):
        self.ensure_one()
        if get_diff_in_sec(self.start_time, self.end_time) <= 0:
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
        self.env.savepoint()
        record = super(OvertimeAndTimeOff, self).create(vals)
        delta = 0.0
        if record.rec_type == 'unpaid':
            delta = record.period_in_hour
        elif record.rec_type == 'timeoff':
            delta = -1 * record.period_in_hour
        balance.hours += delta
        _update_balance(self, vals, record)
        return record

    @api.model
    def write(self, vals):
        _check_balance_enough(self, vals)
        super(OvertimeAndTimeOff, self).update(vals)
        _update_balance(self, vals, )
        return True

    @api.model
    def unlink(self, vals):


    def _check_balance_enough(self, vals):
        Balance = self.env['hs_hr_otb.balance']
        balance = Balance.search([('=','employee_id',self.employee_id.id)])
        balance.ensure_one()
        hours = get_time_diff_in_hour(vals.start_time, vals.end_time)
        if vals.rec_type == 'timeoff' && hours > balance.hours:
            raise Warning('There isn\'t enough time off balance left for this employee!')
        return True

    def _update_balance(self, vals, delta):
        Balance = self.env['hs_hr_otb.balance']
        balance = Balance.search([('=','employee_id',self.employee_id.id)])[0]
        balance.hours += delta
        return True

class Balance(models.Model):
    _name = 'hs_hr_otb.balance'
    name = fields.Char(compute='_balance_name',string='Name',store=True)
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True)

    @api.depends('employee_id')
    def _balance_name(self):
        self.ensure_one()
        if self.employee_id:
            self.name = self.employee_id.name + '-TimeOffBalance'

class Adjustment(models.Model):
    _name = 'hs_hr_otb.adjustment'
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True)
    reason = fields.Char(string='Reason',required=True)
