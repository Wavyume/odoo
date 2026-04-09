from odoo import api, fields, models


class LavastaEmployeeWage(models.Model):
    _name = 'lavasta.employee.wage'
    _description = 'Lavasta Employee Wage by Department'

    employee_id = fields.Many2one('hr.employee', string='Співробітник', ondelete='cascade')
    department_id = fields.Many2one('hr.department', string='Департамент', required=True)
    wage = fields.Float(string='Оклад ₴/сек')

    _sql_constraints = [
        (
            'lavasta_employee_department_unique',
            'unique(employee_id, department_id)',
            'Для кожного департаменту співробітника має бути лише один оклад.',
        ),
    ]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    work_history_ids = fields.One2many('employee.work.history', 'employee_id', string='Історія виконань')
    lavasta_department_ids = fields.Many2many(
        'hr.department',
        'lavasta_employee_department_rel',
        'employee_id',
        'department_id',
        string='Департаменти',
    )
    lavasta_wage_ids = fields.One2many('lavasta.employee.wage', 'employee_id', string='Зарплата')

    @api.onchange('lavasta_department_ids')
    def _onchange_lavasta_department_ids(self):
        for employee in self:
            selected_departments = employee.lavasta_department_ids
            employee.lavasta_wage_ids = employee.lavasta_wage_ids.filtered(
                lambda wage_line: wage_line.department_id in selected_departments
            )

            existing_department_ids = set(employee.lavasta_wage_ids.mapped('department_id').ids)
            for department in selected_departments:
                if department.id not in existing_department_ids:
                    employee.lavasta_wage_ids += self.env['lavasta.employee.wage'].new(
                        {
                            'department_id': department.id,
                            'wage': 0.0,
                        }
                    )