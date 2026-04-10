from odoo import api, fields, models


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    lavasta_history_id = fields.Many2one(
        "employee.work.history",
        string="Lavasta History",
        ondelete="set null",
        copy=False,
    )
    lavasta_qty = fields.Float(
        string="Кількість од.",
        default=1.0,
        help="Кількість одиниць для нарахування; синхронізується з employee.work.history (qty).",
    )

    def _get_lavasta_employee(self):
        self.ensure_one()
        employee = False

        if "employee_id" in self._fields:
            employee = self.employee_id

        if not employee and "user_id" in self._fields and self.user_id:
            employee = self.user_id.employee_id

        return employee

    def _prepare_history_vals(self):
        self.ensure_one()

        employee = self._get_lavasta_employee()
        if not employee:
            return False

        operation = self.env["lavasta.operation.directory"].search(
            [("name", "=", self.workorder_id.name)],
            limit=1,
        )

        date_start = self.date_start
        datetime_value = False
        date_value = False
        if date_start:
            datetime_value = fields.Datetime.to_datetime(date_start)
            date_value = fields.Date.to_date(date_start)

        # In MRP tracking duration is stored in minutes; convert to seconds for history.
        seconds = int((self.duration or 0.0) * 60)

        vals = {
            "employee_id": employee.id,
            "order_id": self.production_id.id if self.production_id else False,
            "operation_id": operation.id if operation else False,
            "seconds": seconds,
            "department_id": employee.department_id.id if employee.department_id else False,
        }

        history_fields = self.env["employee.work.history"]._fields
        if "qty" in history_fields:
            vals["qty"] = self.lavasta_qty
        if "datetime" in history_fields:
            vals["datetime"] = datetime_value
        elif "date" in history_fields:
            vals["date"] = date_value

        return vals

    def _sync_to_employee_history(self):
        history_model = self.env["employee.work.history"]

        for record in self:
            if not (record.duration > 0 or record.date_end):
                continue

            vals = record._prepare_history_vals()
            if not vals:
                continue

            if record.lavasta_history_id:
                record.lavasta_history_id.write(vals)
                continue

            history = history_model.create(vals)
            record.lavasta_history_id = history.id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_to_employee_history()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_to_employee_history()
        return result

    def unlink(self):
        linked_history = self.mapped("lavasta_history_id")
        result = super().unlink()
        if linked_history:
            linked_history.unlink()
        return result
