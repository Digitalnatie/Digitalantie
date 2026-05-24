/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { onMounted, onWillUnmount, useEnv } from "@odoo/owl";

/**
 * Global service: subscribes to the WooCommerce bus channel and broadcasts
 * an OWL env.bus event so any open sale.order list view can auto-reload.
 */
const wooSyncService = {
    dependencies: ["bus_service", "notification", "action"],

    start(env, { bus_service, notification, action }) {
        bus_service.addChannel("sale.order.woo_sync");

        bus_service.addEventListener("notification", ({ detail: notifications }) => {
            for (const { type, payload } of notifications) {
                if (type !== "new_orders") continue;

                // Signal any mounted sale.order list views to reload
                env.bus.trigger("WOO_ORDERS_SYNCED", payload);

                notification.add(
                    `${payload.count} new WooCommerce order(s) from "${payload.instance}"`,
                    {
                        type: "info",
                        sticky: false,
                        buttons: [
                            {
                                name: "View Orders",
                                primary: true,
                                onClick: () =>
                                    action.doAction({
                                        type: "ir.actions.act_window",
                                        name: "Sales Orders",
                                        res_model: "sale.order",
                                        views: [[false, "list"], [false, "form"]],
                                        target: "current",
                                    }),
                            },
                        ],
                    }
                );
            }
        });
    },
};

registry.category("services").add("digitalnatie_woo_sync", wooSyncService);

/**
 * Patch ListController so that any sale.order list auto-reloads when a
 * WOO_ORDERS_SYNCED event fires on env.bus.
 */
patch(ListController.prototype, {
    setup() {
        super.setup();
        const env = useEnv();

        onMounted(() => {
            if (this.props.resModel !== "sale.order") return;
            this._wooSyncHandler = async () => {
                await this.model.load();
            };
            env.bus.addEventListener("WOO_ORDERS_SYNCED", this._wooSyncHandler);
        });

        onWillUnmount(() => {
            if (this._wooSyncHandler) {
                env.bus.removeEventListener("WOO_ORDERS_SYNCED", this._wooSyncHandler);
                this._wooSyncHandler = null;
            }
        });
    },
});
