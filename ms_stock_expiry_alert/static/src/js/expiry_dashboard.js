import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ExpiryDashboard extends Component {
    static template = "ms_stock_expiry.ExpiryDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.kpis = {
            within_threshold: 0,
            critical: 0,
            expired: 0,
            value_at_risk: 0,
        };

        this.lots = [];
        this.loading = true;

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.loading = true;

        try {
            const [kpis, lots] = await Promise.all([
                this.orm.call(
                    "stock.lot",
                    "get_expiry_dashboard_kpis",
                    []
                ),
                this.orm.call(
                    "stock.lot",
                    "get_expiry_dashboard_lots",
                    []
                ),
            ]);

            this.kpis = kpis;
            this.lots = lots;
        } finally {
            this.loading = false;
        }
    }

    async refreshDashboard() {
        await this.loadDashboard();

        this.notification.add(
            "Dashboard refreshed successfully.",
            {
                type: "success",
            }
        );
    }

    openFilteredLots(domain, title) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "stock.lot",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: domain,
        });
    }

    openLot(lotId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.lot",
            views: [
                [false, "form"],
            ],
            res_id: lotId,
            target: "current",
        });
    }

    async notifyLot(lotId) {
        try {
            await this.orm.call(
                "stock.lot",
                "action_notify_expiry",
                [[lotId]]
            );

            this.notification.add(
                "Expiry notification sent successfully.",
                {
                    type: "success",
                }
            );

            await this.loadDashboard();

        } catch (error) {
            throw error;
        }
    }

    formatQuantity(quantity) {
        if (quantity === undefined || quantity === null) {
            return "0";
        }

        return Number(quantity).toLocaleString(
            undefined,
            {
                maximumFractionDigits: 2,
            }
        );
    }

    formatCurrency(value) {
        if (value === undefined || value === null) {
            return "0.00";
        }

        return Number(value).toLocaleString(
            undefined,
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }
        );
    }
}

registry.category("actions").add(
    "ms_stock_expiry_dashboard_tag",
    ExpiryDashboard
);