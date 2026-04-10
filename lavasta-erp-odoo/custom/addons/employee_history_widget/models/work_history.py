from odoo import models, fields, api

class EmployeeWorkHistory(models.Model):
    _name = 'employee.work.history'
    _description = 'Історія виконань співробітника'
    _order = 'datetime desc' # Сортировка от новых к старым

    employee_id = fields.Many2one('hr.employee', string='Співробітник', required=True, ondelete='cascade')
    datetime = fields.Datetime(string='Дата та час', default=fields.Datetime.now)
    order_id = fields.Many2one('mrp.production', string='Замовлення')
    operation_id = fields.Many2one(
        'lavasta.operation.directory',
        string='Операція зі специфікації',
    )
    department_id = fields.Many2one('hr.department', string='Департамент')
    
    seconds = fields.Integer(string='Секунд (факт)')
    rate = fields.Float(string='Рейт (₴/сек)')
    qty = fields.Float(string='Кількість операцій', default=1.0)
    
    # Автоматический подсчет ЗП прямо в Python!
    accrued = fields.Float(string='Нараховано (₴)', compute='_compute_accrued', store=True)

    @api.depends('seconds', 'rate', 'qty')
    def _compute_accrued(self):
        for record in self:
            record.accrued = record.seconds * record.rate * record.qty

    @api.onchange('employee_id', 'department_id')
    def _onchange_lavasta_employee_department_set_rate(self):
        for record in self:
            record.rate = 0.0
            if not record.employee_id or not record.department_id:
                continue

            wage_line = record.employee_id.lavasta_wage_ids.filtered(
                lambda line: line.department_id == record.department_id
            )[:1]
            if wage_line:
                record.rate = wage_line.wage