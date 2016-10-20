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

def build_balance_name(employee_name):
    return employee_name + '-TimeOffBalance'

class BaseAttendanceRecord(models.AbstractModel):
    _name = 'hs_hr_otb.base_attendance_record'
    name = fields.Char(compute='_record_name',store=True)
    employee_id = fields.Many2one('res.partner',string='Employee')
    start_time = fields.Datetime(string='From',default=get_default_datetime())
    end_time = fields.Datetime(string='To',default=get_default_datetime())
    hours = fields.Float(compute='_hours',string='Hours',readonly=True,store=True)
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
    def _hours(self):
        for record in self:
            if record.start_time and record.end_time:
                # the unit for counting is 0.5 hour
                record.hours = get_time_diff_in_hour(record.start_time, record.end_time)

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
        cr = self.env.cr
        cr.execute('SAVEPOINT create_otto_record')
        try:
            record = super(OvertimeAndTimeOff, self).create(vals)
            employee_id = int(vals['employee_id'])
            employee = self.env['res.partner'].search([('id','=',employee_id)])
            delta = 0.0
            if record.rec_type == 'unpaid':
                delta = record.hours
            elif record.rec_type == 'timeoff':
                delta = -1 * record.hours
            if delta != 0:
                Balance = self.env['hs_hr_otb.balance']
                balance = Balance.search([('employee_id','=',employee_id)])
                if len(balance) == 0:
                    balance = Balance.create({
                        'employee_id': employee_id,
                        'name': build_balance_name(employee.name),
                        'hours': 0.0
                    })
                if delta < 0 and balance.hours - delta < 0:
                    cr.execute('ROLLBACK TO SAVEPOINT create_otto_record')
                    raise Warning('There isn\'t enough time off balance left for this employee!')
                else:
                    balance.hours += delta
            return record
        except Exception as e:
            cr.execute('ROLLBACK TO SAVEPOINT create_otto_record')
            _show_uncaught_exception(e)

    @api.multi
    def write(self, vals):
        cr = self.env.cr
        cr.execute('SAVEPOINT write_otto_record')
        try:
            super(OvertimeAndTimeOff, self).write(vals)
            self._recalculate_balance()
            return True
        except Exception as e:
            cr.execute('ROLLBACK')
            self._show_uncaught_exception(e)

    def unlink(self, cr, uid, ids, context=None):
        cr.execute('SAVEPOINT unlink_otto_record')
        try:
            super(OvertimeAndTimeOff, self).unlink(cr, uid, ids, context)
            self._recalculate_balance(cr)
        except Exception as e:
            cr.execute('ROLLBACK')
            self._show_uncaught_exception(e)

    def _recalculate_balance(self, cr):
        try:
            cr.execute('''
                UPDATE hs_hr_otb_balance AS b
                SET hours = h.hours
                FROM (
                    SELECT employee_id, SUM(
                        CASE rec_type
                        WHEN 'unpaid' THEN hours
                        WHEN 'timeoff' THEN hours*-1
                        WHEN 'paid' THEN 0
                        END
                    ) AS hours
                    FROM hs_hr_otb_otto
                    GROUP BY employee_id
                ) AS h
                WHERE b.employee_id = h.employee_id
                    AND b.hours != h.hours
            ''')
            cr.commit()
        except Exception as e:
            cr.execute('ROLLBACK')
            self._show_uncaught_exception(e)

    def _show_uncaught_exception(self, e):
        raise Warning('There is an error processing your request. Exception detail: %s' % e)

class Balance(models.Model):
    _name = 'hs_hr_otb.balance'
    name = fields.Char(compute='_record_name',string='Name',store=True)
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True,default=0)

    @api.depends('employee_id')
    def _record_name(self):
        self.ensure_one()
        if self.employee_id:
            self.name = build_balance_name(self.employee_id.name)

class Adjustment(models.Model):
    _name = 'hs_hr_otb.adjustment'
    employee_id = fields.Many2one('res.partner',string='Employee')
    hours = fields.Float(string='Hours',required=True)
    reason = fields.Char(string='Reason',required=True)
