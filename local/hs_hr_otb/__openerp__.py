# -*- coding: utf-8 -*-
{
    'name': 'Employee Overtime and Time Off Management',
    'summary': 'Manage employee shifts, attendance, overtime and leave etc.',
    'description': 'To be described',
    'author': 'Guo Yufeng',
    'category': 'Hengshen HR',
    'version': '1.0.0',
    'depends': ['base','hr'],
    'data': [
        'views/hs_hr_otb_view.xml',
        'security/groups.xml',
        'security/ir.model.access.csv',
    ]
}
