# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
from datetime import datetime
import time

def get_datetime(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

def get_time_diff_in_hour(start_time_str, end_time_str):
    secs = (get_datetime(end_time_str) - get_datetime(start_time_str)).total_seconds()
    return round((secs - 3600 if secs >= 5 * 3600 else secs)/1800.0, 0) * 0.5

def get_default_datetime():
    return datetime.combine(datetime.today(), datetime.min.time())

def show_uncaught_exception(e):
    raise Warning('There is an error processing your request. Exception detail: %s' % e)

def recalculate_balance(cr):
    try:
        cr.execute('''
        UPDATE hs_hr_otb_balance AS b
        SET hours = COALESCE(h.hours, CAST(0 AS double precision)) + COALESCE(a.hours, CAST(0 AS double precision))
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
        FULL JOIN (
        SELECT employee_id, SUM(hours) as hours
        FROM hs_hr_otb_adjustment
        GROUP BY employee_id
        ) a ON h.employee_id = a.employee_id
        WHERE b.employee_id = h.employee_id
        AND b.hours != COALESCE(h.hours, CAST(0 AS double precision)) + COALESCE(a.hours, CAST(0 AS double precision))
        ''')
        cr.commit()
    except Exception as e:
        cr.execute('ROLLBACK')
        show_uncaught_exception(e)

class BaseAttendanceRecord(models.AbstractModel):
    _name = 'hs_hr_otb.base_attendance_record'
    name = fields.Char(compute='_record_name',store=True)
    employee_id = fields.Many2one('hr.employee',string='Employee',required=True)
    start_time = fields.Datetime(string='Start Time',default=get_default_datetime(),required=True)
    end_time = fields.Datetime(string='End Time',default=get_default_datetime(),required=True)
    hours = fields.Float(string='Hours',required=True)
    reason = fields.Char(string='Reason')
    # once a record is archived, it cannot be edited or deleted
    archived = fields.Boolean(string='Archived?',default=False)

    @api.multi
    @api.depends('employee_id', 'start_time')
    def _record_name(self):
        for record in self:
            if record.employee_id and record.start_time:
                record.name = record.employee_id.name + '-' + get_datetime(record.start_time).strftime('%Y%m%d_%H%M')

    # manually fill this field
    # @api.multi
    # @api.depends('start_time', 'end_time')
    # def _hours(self):
    #     for record in self:
    #         if record.start_time and record.end_time:
    #             # the unit for counting is 0.5 hour
    #             record.hours = get_time_diff_in_hour(record.start_time, record.end_time)

    @api.constrains('start_time', 'end_time')
    def _check_time_period(self):
        for record in self:
            if get_datetime(record.start_time) >= get_datetime(record.end_time):
                raise ValidationError(_("End time must be later than start time!"))

    @api.constrains('hours')
    def _check_hours(self):
        for record in self:
            if record.hours < 0:
                raise ValidationError(_("Hours should be positive!"))
                # return False
            elif record.hours % 0.5 != 0:
                raise ValidationError(_("The minimum unit is 0.5 hour!"))
                # return False
        return False

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
            employee_id = int(vals['employee_id'])
            employee = self.env['hr.employee'].search([('id','=',employee_id)])
            check_clerk_auth(self.env,[employee.department_id.id],self.env.uid)
            record = super(OvertimeAndTimeOff, self).create(vals)
            delta = 0.0
            if record.rec_type == 'unpaid':
                delta = record.hours
            elif record.rec_type == 'timeoff':
                delta = -1 * record.hours
            if delta != 0:
                Balance = self.env['hs_hr_otb.balance'].sudo()
                balance = Balance.search([('employee_id','=',employee_id)])
                if len(balance) == 0:
                    balance = Balance.create({
                        'employee_id': employee_id,
                        'hours': 0.0
                    })
                if delta < 0 and balance.hours - delta < 0:
                    cr.execute('ROLLBACK TO SAVEPOINT create_otto_record')
                    raise Warning(_('There isn\'t enough time off balance left for this employee!'))
                else:
                    balance.hours += delta
            return record
        except Exception as e:
            cr.execute('ROLLBACK TO SAVEPOINT create_otto_record')
            if isinstance(e,ValidationError):
                raise
            else:
                show_uncaught_exception(e)

    @api.multi
    def write(self, vals):
        cr = self.env.cr
        cr.execute('SAVEPOINT write_otto_record')
        try:
            # employee = self.env['hr.employee'].search([('id','=',employee_id)])
            employee = self.employee_id
            check_clerk_auth(self.env,[employee.department_id.id],self.env.user.id)
            super(OvertimeAndTimeOff, self).write(vals)
            recalculate_balance(cr)
            return True
        except Exception as e:
            cr.execute('ROLLBACK')
            if isinstance(e,ValidationError):
                raise
            else:
                show_uncaught_exception(e)

    def unlink(self, cr, uid, ids, context=None):
        cr.execute('SAVEPOINT unlink_otto_record')
        try:
            env = api.Environment(cr, uid, context)
            department_ids = []
            for record in env['hs_hr_otb.otto'].search([('id','in',ids)]):
                department_id = record.employee_id.department_id.id
                if not department_id:
                    raise ValidationError(_('Cannot find %s\'s department') % record.employee_id.name)
                elif department_id not in department_ids:
                    department_ids.append(department_id)
            check_clerk_auth(env,department_ids,uid)
            super(OvertimeAndTimeOff, self).unlink(cr, uid, ids, context)
            recalculate_balance(cr)
        except Exception as e:
            cr.execute('ROLLBACK')
            if isinstance(e,ValidationError):
                raise
            else:
                show_uncaught_exception(e)



class Balance(models.Model):
    _name = 'hs_hr_otb.balance'
    _rec_name = 'employee_id'
    employee_id = fields.Many2one('hr.employee',string='Employee')
    hours = fields.Float(string='Hours',required=True,default=0)

class Adjustment(models.Model):
    _name = 'hs_hr_otb.adjustment'
    employee_id = fields.Many2one('hr.employee',string='Employee')
    hours = fields.Float(string='Hours',required=True)
    reason = fields.Char(string='Reason')
    rec_type = fields.Selection(
        string='Type',
        required=True,
        default='init',
        translation=True,
        selection=[
        ('init', 'Initialization'),
        ('pay_in_lieu', 'Pay In Lieu')
    ])

    @api.constrains('hours')
    def _check_hours(self):
        for record in self:
            if record.hours % 0.5 != 0:
                raise ValidationError(_("The minimum unit is 0.5 hour!"))

    @api.model
    def create(self, vals):
        cr = self.env.cr
        cr.execute('SAVEPOINT create_adjustment_record')
        try:
            record = super(Adjustment, self).create(vals)
            employee_id = int(vals['employee_id'])
            employee = self.env['hr.employee'].search([('id','=',employee_id)])
            hours = float(vals['hours'])
            Balance = self.env['hs_hr_otb.balance'].sudo()
            balance = Balance.search([('employee_id','=',employee_id)])
            if len(balance) == 0:
                balance = Balance.create({
                    'employee_id': employee_id,
                    'hours': hours
                })
            else:
                balance.hours += hours
            return record
        except Exception as e:
            cr.execute('ROLLBACK TO SAVEPOINT create_adjustment_record')
            if isinstance(e,ValidationError):
                raise
            else:
                show_uncaught_exception(e)

    @api.multi
    def write(self, vals):
        cr = self.env.cr
        cr.execute('SAVEPOINT write_adjustment_record')
        try:
            super(Adjustment, self).write(vals)
            recalculate_balance(cr)
            return True
        except Exception as e:
            cr.execute('ROLLBACK')
            if isinstance(e,ValidationError):
                raise
            else:
                show_uncaught_exception(e)

    def unlink(self, cr, uid, ids, context=None):
        cr.execute('SAVEPOINT unlink_adjustment_record')
        try:
            super(Adjustment, self).unlink(cr, uid, ids, context)
            recalculate_balance(cr)
        except Exception as e:
            cr.execute('ROLLBACK')
            if isinstance(e,ValidationError):
                raise
            else:
                show_uncaught_exception(e)

class Clerk(models.Model):
    _name = 'hs_hr_otb.clerk'
    department_id = fields.Many2one('hr.department',string='Department')
    user_id = fields.Many2one('res.users',string='User',required=True)

    _sql_constraints = [
        ('hs_hr_otb_clerk_uniq',
        'UNIQUE (department_id, user_id)',
        'Same department attendance clerk already exsits')
    ]

def check_clerk_auth(env, department_ids, user_id):
    auth_department_ids = [
        record.department_id.id for record in env['hs_hr_otb.clerk'].sudo().search([('user_id','=',user_id)])
    ]
    user = env['res.users'].search([('id','=',user_id)])
    # if user is in group_hs_hr_otb_clerk, should check if user has the permission to handle the department's data
    if env.ref('hs_hr_otb.group_hs_hr_otb_clerk') in user.groups_id and \
    len(set(department_ids).difference(set(auth_department_ids)))>0:
        raise ValidationError(_('No sufficient permission for this action!'))
    return True
