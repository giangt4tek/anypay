/** @odoo-module **/
import { WebClient } from "@web/webclient/webclient";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { onWillStart, useState, onMounted } from "@odoo/owl";
patch(WebClient.prototype, {
  setup() {
    super.setup();
  },

  async _loadDefaultApp() {
    // Selects the first root menu if any
    let root;
    let firstApp;
    if (await user.hasGroup("base.group_system"))
      return super._loadDefaultApp();

    if (await user.hasGroup("anypay_wallet.user_wallet")) {
      const filteredArray = this.menuService
        .getApps()
        .filter(
          (item) => item.xmlid === "anypay_wallet.menu_t4tek_wallet_root"
        );
      root = filteredArray[0];
      firstApp = root.appID;
    } 
    if (firstApp) {
      return this.menuService.selectMenu(firstApp);
    }
  },
});