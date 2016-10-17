# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time, datetime

def get_datetime(date_str):
    return datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

def get_diff_in_sec(start_time_str, end_time_str):
    return (get_datetime(end_time_str) - get_datetime(start_time_str)).seconds

class BaseAttendanceRecord(models.AbstractModel):
    _name = 'hs_hr_otb.base_attendance_record'
    name = fields.Char(compute='_record_name',required=True,store=True)
    employee_id = fields.Many2one('res.partner',string='Employee')
    # date = fields.Date(compute='_record_date',string='Date',store=True,readonly=True)
    start_time = fields.Datetime(string='From')
    end_time = fields.Datetime(string='To')
    period = fields.Float(compute='_period',string='Period',store=True,readonly=True)
    period_in_hour = fields.Float(compute='_period_in_hour',string='Hours',readonly=True)
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
    def _period(self):
        for record in self:
            if record.start_time and record.end_time:
                record.period = get_diff_in_sec(record.end_time, record.start_time)
            else:
                record.period = 0

    @api.multi
    @api.depends('start_time', 'end_time')
    def _period_in_hour(self):
        for record in self:
            hours = 0
            if record.start_time and record.end_time:
                # 最小的时数单位为半个小时
                hours = round(get_diff_in_sec(record.end_time, record.start_time) / 1800.0, 0) * 0.5
            record.period_in_hour = '%.2f' % hours

class OvertimeAndTimeOff(models.Model):
    _name = 'hs_hr_otb.otto'
    _inherit = ['hs_hr_otb.base_attendance_record']

class Balance(models.Model):
    _name = 'hs_hr_otb.balance'
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True)

class Adjustment(models.Model):
    _name = 'hs_hr_otb.adjustment'
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True)
    reason = fields.Char(string='Reason',required=True)
