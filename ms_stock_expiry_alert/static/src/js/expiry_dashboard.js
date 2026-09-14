import { Component, useState, onWillStart } from "@odoo/owl";
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

        this.state = useState({
            currentPage: 1,
            pageSize: 10, 
        });

        this.lots = [];
        this.loading = true;

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    get totalLots() {
        return this.lots.length;
    }

    get paginatedLots() {
        const start = (this.state.currentPage - 1) * this.state.pageSize;
        const end = start + this.state.pageSize;
        return this.lots.slice(start, end);
    }

    get pageRangeText() {
        if (this.totalLots === 0) return "0-0 / 0";
        const start = (this.state.currentPage - 1) * this.state.pageSize + 1;
        const end = Math.min(this.state.currentPage * this.state.pageSize, this.totalLots);
        return `${start}-${end} / ${this.totalLots}`;
    }

    changePage(delta) {
        const maxPage = Math.ceil(this.totalLots / this.state.pageSize) || 1;
        const newPage = this.state.currentPage + delta;
        if (newPage >= 1 && newPage <= maxPage) {
            this.state.currentPage = newPage;
        }
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
            const res = await this.orm.call(
                "stock.lot",
                "action_notify_expiry",
                [[lotId]]
            );

            if (res && res.type === "ir.actions.client") {
                await this.action.doAction(res);
            } else {
                this.notification.add(
                    "Expiry notification sent successfully.",
                    {
                        type: "success",
                    }
                );
            }

            await this.loadDashboard();

        } catch (error) {
            const errorMsg = error.data?.message || error.message || "Failed to send notification.";

            this.notification.add(
                errorMsg,
                {
                    title: "Warning",
                    type: "warning",
                    sticky: false,
                }
            );
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