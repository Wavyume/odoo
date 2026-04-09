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

    @staticmethod
    def _sanitize_lavasta_wage_commands(commands):
        if not commands:
            return commands

        sanitized = []
        for command in commands:
            if not isinstance(command, (list, tuple)) or len(command) < 1:
                sanitized.append(command)
                continue

            operation = command[0]
            values = command[2] if len(command) > 2 and isinstance(command[2], dict) else {}

            # Skip creating empty lines without required department_id.
            if operation == 0 and not values.get('department_id'):
                continue

            sanitized.append(command)

        return sanitized

    def _sync_lavasta_wages(self):
        wage_model = self.env['lavasta.employee.wage']
        for employee in self:
            selected_department_ids = set(employee.lavasta_department_ids.ids)
            existing_wages = employee.lavasta_wage_ids

            # Remove wages for departments that are no longer selected.
            wages_to_remove = existing_wages.filtered(
                lambda wage_line: wage_line.department_id.id not in selected_department_ids
            )
            if wages_to_remove:
                wages_to_remove.unlink()

            # Create wages only for newly selected departments.
            existing_department_ids = set(employee.lavasta_wage_ids.mapped('department_id').ids)
            missing_department_ids = selected_department_ids - existing_department_ids
            for department_id in missing_department_ids:
                wage_model.create(
                    {
                        'employee_id': employee.id,
                        'department_id': department_id,
                        'wage': 0.0,
                    }
                )

    @api.onchange('lavasta_department_ids')
    def _onchange_lavasta_department_ids(self):
        for employee in self:
            selected_department_ids = set(employee.lavasta_department_ids.ids)
            current_lines = employee.lavasta_wage_ids

            lines_to_keep = current_lines.filtered(
                lambda wage_line: wage_line.department_id.id in selected_department_ids
            )
            existing_department_ids = set(lines_to_keep.mapped('department_id').ids)

            new_lines = self.env['lavasta.employee.wage']
            for department_id in selected_department_ids - existing_department_ids:
                new_lines += self.env['lavasta.employee.wage'].new(
                    {
                        'department_id': department_id,
                        'wage': 0.0,
                    }
                )

            employee.lavasta_wage_ids = lines_to_keep + new_lines

    @api.onchange('department_id')
    def _onchange_department_id_append_lavasta(self):
        for employee in self:
            if employee.department_id and employee.department_id not in employee.lavasta_department_ids:
                employee.lavasta_department_ids |= employee.department_id
                employee._onchange_lavasta_department_ids()

    def write(self, vals):
        if 'lavasta_wage_ids' in vals:
            vals['lavasta_wage_ids'] = self._sanitize_lavasta_wage_commands(vals['lavasta_wage_ids'])

        result = super().write(vals)
        if 'lavasta_department_ids' in vals:
            self._sync_lavasta_wages()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'lavasta_wage_ids' in vals:
                vals['lavasta_wage_ids'] = self._sanitize_lavasta_wage_commands(vals['lavasta_wage_ids'])

        employees = super().create(vals_list)

        employees_to_sync = employees.filtered(lambda emp: emp.lavasta_department_ids)
        if employees_to_sync:
            employees_to_sync._sync_lavasta_wages()
        return employees