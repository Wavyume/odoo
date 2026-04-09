from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    lavasta_attendance_status = fields.Selection(
        selection=[
            ("unconfirmed", "Не підтверджено"),
            ("confirmed", "Підтверджено"),
        ],
        string="Статус",
        default="unconfirmed",
        required=True,
        copy=False,
    )

    def action_lavasta_confirm_attendance(self):
        self.write({"lavasta_attendance_status": "confirmed"})
        return True
