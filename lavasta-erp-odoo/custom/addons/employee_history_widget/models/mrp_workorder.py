# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    # Тривалість з Telegram-бота (години або хвилини — як прийнято у вашому боті)
    lavasta_individual_duration = fields.Float(
        string='Індивідуальна тривалість',
        help='Значення надходить з Telegram-бота.',
    )

    lavasta_it_status = fields.Selection(
        selection=[
            ('draft', 'Чернетка'),
            ('pending', 'Очікує'),
            ('confirmed', 'Підтверджено'),
            ('rejected', 'Відхилено'),
        ],
        string='Статус ІТ',
        default='draft',
        required=True,
        copy=False,
    )

    def write(self, vals):
        # Запам’ятовуємо записи, у яких статус саме зараз зміниться на «Підтверджено»
        becoming_confirmed = self.env['mrp.workorder']
        if vals.get('lavasta_it_status') == 'confirmed':
            becoming_confirmed = self.filtered(lambda wo: wo.lavasta_it_status != 'confirmed')

        res = super().write(vals)

        # Після оновлення: скопіювати індивідуальну тривалість у стандартне поле
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
