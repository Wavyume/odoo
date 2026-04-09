from odoo import models, fields, api

class EmployeeWorkHistory(models.Model):
    _name = 'employee.work.history'
    _description = 'Історія виконань співробітника'
    _order = 'datetime desc' # Сортировка от новых к старым

    employee_id = fields.Many2one('hr.employee', string='Співробітник', required=True, ondelete='cascade')
    datetime = fields.Datetime(string='Дата та час', default=fields.Datetime.now)
    order = fields.Char(string='Замовлення')
    spec_op = fields.Char(string='Операція зі специфікації')
    fact_op = fields.Char(string='Операція (факт)')
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