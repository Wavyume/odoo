from odoo import api, fields, models


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

    _sql_constraints = [
        (
            'lavasta_operation_directory_name_unique',
            'unique(name)',
            'Операція з такою назвою вже існує.',
        ),
    ]

    def _sync_from_mrp_operations(self):
        if self.env.context.get('lavasta_operation_sync_done'):
            return

        existing_names = set(
            self.with_context(lavasta_operation_sync_done=True).search([]).mapped('name')
        )
        values_to_create = []

        # 1. Тянем из шаблонов (Специфікації)
        for mrp_op in self.env['mrp.routing.workcenter'].search([]):
            op_name = (mrp_op.name or '').strip()
            if op_name and op_name not in existing_names:
                seconds = int(mrp_op.time_cycle_manual * 60) if 'time_cycle_manual' in mrp_op._fields and mrp_op.time_cycle_manual else 0
                values_to_create.append({'name': op_name, 'execution_seconds': seconds})
                existing_names.add(op_name)

        # 2. Тянем из реальных заказов (Робочі замовлення)
        for workorder in self.env['mrp.workorder'].search([]):
            op_name = (workorder.name or '').strip()
            if op_name and op_name not in existing_names:
                seconds = int(workorder.duration_expected * 60) if 'duration_expected' in workorder._fields and workorder.duration_expected else 0
                values_to_create.append({'name': op_name, 'execution_seconds': seconds})
                existing_names.add(op_name)

        if values_to_create:
            self.with_context(lavasta_operation_sync_done=True).create(values_to_create)

    @api.model
    def web_search_read(self, *args, **kwargs):
        # Odoo UI вызывает именно web_search_read.
        # Используем универсальную сигнатуру, чтобы не ломаться на различиях
        # между версиями/патчами Odoo.
        self._sync_from_mrp_operations()
        return super().web_search_read(*args, **kwargs)

    @api.model
    def action_open_new_modal(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Нова операція',
            'res_model': 'lavasta.operation.directory',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_edit_modal(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Редагування операції',
            'res_model': 'lavasta.operation.directory',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_delete_record(self):
        self.ensure_one()
        self.sudo().unlink()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
