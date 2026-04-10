# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    lavasta_total_qty = fields.Float(
        string='Кількість',
        compute='_compute_lavasta_total_qty',
        store=True,
        readonly=True,
        help='Сума полів «Кількість од.» (lavasta_qty) у записах Time Tracking (time_ids).',
    )

    @api.depends('time_ids', 'time_ids.lavasta_qty')
    def _compute_lavasta_total_qty(self):
        for wo in self:
            wo.lavasta_total_qty = sum(wo.time_ids.mapped('lavasta_qty'))

    # Тривалість з Telegram-бота (години або хвилини — як прийнято у вашому боті)
    lavasta_individual_duration = fields.Float(
        string='Індивідуальна тривалість',
        help='Значення надходить з Telegram-бота.',
    )

    lavasta_it_status = fields.Selection(
        selection=[
            ('confirmed', 'Підтверджено'),
            ('not_confirmed', 'Не підтверджено'),
        ],
        string='Статус ІТ',
        copy=False,
    )

    def write(self, vals):
        # Запам'ятовуємо записи, у яких статус саме зараз зміниться на "Підтверджено".
        becoming_confirmed = self.env['mrp.workorder']
        if vals.get('lavasta_it_status') == 'confirmed':
            becoming_confirmed = self.filtered(lambda wo: wo.lavasta_it_status != 'confirmed')

        # Якщо приходить індивідуальна тривалість без явного статусу,
        # то для записів з порожнім статусом автоматично ставимо "Не підтверджено".
        has_duration_update = 'lavasta_individual_duration' in vals
        has_explicit_status = 'lavasta_it_status' in vals

        if has_duration_update and not has_explicit_status:
            empty_status_records = self.filtered(lambda wo: not wo.lavasta_it_status)
            regular_records = self - empty_status_records

            res = True
            if regular_records:
                res = super(MrpWorkorder, regular_records).write(vals)
            if empty_status_records:
                vals_with_auto_status = dict(vals, lavasta_it_status='not_confirmed')
                res_empty = super(MrpWorkorder, empty_status_records).write(vals_with_auto_status)
                res = res and res_empty
        else:
            res = super().write(vals)

        # Після оновлення: скопіювати індивідуальну тривалість у стандартне поле
        # тільки якщо статус явно переведено в "Підтверджено".
        if vals.get('lavasta_it_status') == 'confirmed' and becoming_confirmed:
            for wo in becoming_confirmed:
                if wo.lavasta_it_status == 'confirmed':
                    # super().write, щоб уникнути зайвої рекурсії під час каскадних перевизначень write
                    super(MrpWorkorder, wo).write({
                        'duration_expected': wo.lavasta_individual_duration,
                    })

        return res

    def action_confirm_it_status(self):
        """
        Виклик з Telegram-бота (RPC): підтвердити статус і оновити duration_expected через write().
        Підтримує кілька записів у recordset.
        """
        self.write({'lavasta_it_status': 'confirmed'})
        return True
