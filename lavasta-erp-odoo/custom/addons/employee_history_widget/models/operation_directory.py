from odoo import fields, models


class LavastaOperationDirectory(models.Model):
    _name = 'lavasta.operation.directory'
    _description = 'Довідник операцій'

    name = fields.Char(string='Назва операції', required=True)
    department_id = fields.Many2one(
        'hr.department',
        string='Департамент операції',
    )
    execution_seconds = fields.Integer(
        string='Кількість секунд на виконання операції',
    )
