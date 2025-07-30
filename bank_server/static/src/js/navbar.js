
/** @odoo-module **/
import { NavBar } from "@web/webclient/navbar/navbar";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { onWillStart, useState, onMounted } from "@odoo/owl";
import { user } from "@web/core/user";

patch(NavBar.prototype, {
  setup() {
    super.setup(...arguments);
    this.state = useState({
      ...super.state,
      isSeller: false,
      actionSellerAppID: 0,
    });
    onWillStart(async () => {
      const menuItems = this.menuService.getApps();
      console.log(menuItems)
        debugger;
      if (await user.hasGroup("base.group_system")) return;
      if (await user.hasGroup("bank_server.user_bank")) {
        const rootMenuItem = menuItems.find(
          (item) => item.xmlid === "bank_server.menu_t4tek_bank_root"
        );
        this.state.isSeller = true;
        this.state.actionSellerAppID = rootMenuItem?.actionID;
      } 
    });
  },

  get homeButton() {
    return {
      type: "button",
      id: "home-menu-button",
      title: "Home Menu",
      icon: "oi oi-apps",
      callback: () => this.onHomeButtonClick(),
    };
  },

  async onHomeButtonClick() {
    await this.env.services.action.doAction(this.state.actionSellerAppID, {
      clearBreadcrumbs: true,
    });
  },

  trigger(event) {
    const { detail } = event;
    this.messageCallback(detail.crypto_wallet);
  },
  onRecharge() {
    this.vnpay.onRecharge(this.state.partner_id, this.state.crypto_wallet);
  },
  messageCallback(crypto_wallet) {
    this.state.crypto_wallet = crypto_wallet;
  },
});
