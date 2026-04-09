from odoo import models, fields

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    work_history_ids = fields.One2many('employee.work.history', 'employee_id', string='Історія виконань')