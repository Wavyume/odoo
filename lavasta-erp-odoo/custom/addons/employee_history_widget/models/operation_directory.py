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

    _sql_constraints = [
        (
            'lavasta_operation_directory_name_unique',
            'unique(name)',
            'Операція з такою назвою вже існує.',
        ),
    ]

    def _prepare_execution_seconds_from_mrp(self, mrp_operation):
        if 'time_cycle_manual' in mrp_operation._fields and mrp_operation.time_cycle_manual:
            # In MRP this value is usually stored in minutes.
            return int(mrp_operation.time_cycle_manual * 60)
        return 0

    def _sync_from_mrp_operations(self):
        if self.env.context.get('lavasta_operation_sync_done'):
            return

        mrp_operation_model = self.env['mrp.routing.workcenter']
        existing_names = set(
            self.with_context(lavasta_operation_sync_done=True).search([]).mapped('name')
        )

        values_to_create = []
        for mrp_operation in mrp_operation_model.search([]):
            operation_name = (mrp_operation.name or '').strip()
            if not operation_name or operation_name in existing_names:
                continue

            values_to_create.append(
                {
                    'name': operation_name,
                    'execution_seconds': self._prepare_execution_seconds_from_mrp(mrp_operation),
                }
            )
            existing_names.add(operation_name)

        if values_to_create:
            self.with_context(lavasta_operation_sync_done=True).create(values_to_create)

    def search(self, domain, offset=0, limit=None, order=None):
        self._sync_from_mrp_operations()
        return super().search(domain, offset=offset, limit=limit, order=order)

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
        self.unlink()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
