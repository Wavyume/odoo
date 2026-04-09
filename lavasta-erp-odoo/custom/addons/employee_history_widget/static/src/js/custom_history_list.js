/** @odoo-module **/

import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { registry } from "@web/core/registry";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CustomHistoryPanel extends X2ManyField {
    static template = "EmployeeHistoryWidget.HistoryPanel";

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.state = useState({ searchQuery: "" });
    }

    get panelStats() {
        const records = this.list?.records || [];
        let qty = 0; let seconds = 0; let accrued = 0;

        for (const rec of records) {
            qty += rec.data.qty || 0;
            seconds += rec.data.seconds || 0;
            accrued += rec.data.accrued || 0;
        }

        return {
            count: records.length,
            qty: qty,
            seconds: seconds,
            accrued: accrued.toFixed(2)
        };
    }

    async onAddRecord() {
        const employeeId = this.props.record.resId || this.props.record.data.id;
        await this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'employee.work.history', // Вызываем нашу новую Python-модель
            views: [[false, 'form']],
            target: 'new',
            context: {
                ...this.props.context,
                default_employee_id: employeeId,
            }
        }, {
            onClose: () => this.props.record.load()
        });
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }
}

export const customHistoryPanelField = {
    ...x2ManyField,
    component: CustomHistoryPanel,
};

registry.category("fields").add("custom_history_panel", customHistoryPanelField);