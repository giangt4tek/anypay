/** @odoo-module **/
import { Component, onWillStart, markup, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { View } from "@web/views/view";        // ✅ OWL View Component
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { user } from "@web/core/user";

let company_id = 0;

export class TransactionDashboard extends Component {
  setup() {

    this.baseViewProps = {
      display: { searchPanel: false },
      editable: false,
      noBreadcrumbs: true,
      showButtons: false,
    };
    

    this.viewService = useService("view");  // ✅ inject viewService
    this.orm = useService("orm");
    this.company = useService("company");
    this.dialog = useService("dialog");
    this.notification = useService("notification");
    this.state = useState({
          views: [],
          resId: null,
          acc_number: '',
          balance_total: 0,
          domain: [],
          bankList: [],
          transactionType:'',
          transactionTab: "transaction_all",
        });

     this.tabList = [
      { type: "transaction_all", label: "Tất cả giao dịch" },
      { type: "deposit", label: "Nạp tiền" },
      { type: "withdrawal", label: "Rút tiền" },
      { type: "transfer_out", label: "Chuyển khoản" },
      { type: "transfer_in", label: "Nhận khoản" },
      { type: "payment", label: "Thanh toán" },
    ];

    this.action = useService("action");
    this.env.bus.addEventListener("update_balance_total", (event) => {
      const { detail } = event;
     
     let raw_balance = this.state.balance_total.replace(/\./g, '').replace(/[^\d]/g, '');
     let balance_total = parseInt(raw_balance);
     let new_total = 0
     if(detail.transactionType === 'deposit')
        new_total = balance_total + detail.monneyAmount;
     if(detail.transactionType === 'withdrawal' || detail.transactionType === 'transfer_out') 
        new_total = balance_total - detail.monneyAmount;
     
     this.state.balance_total = new_total.toLocaleString("vi-VN") + " VNĐ";

    });
    onWillStart(async () => {
              await this.initialize();     // gán acc_number, balance, v.v.
              await this.loadViewData(); });
    this.switchTab = this.switchTab.bind(this);
    
    
    //onWillStart(async () => await this.initialize());

  }



  async onChangeCompany() {
    company_id = parseInt(this.state.company_id);
    const actionRequest = {
      id: this.props.action.id,
      type: "ir.actions.client",
      tag: "bank_server.transaction_dashboard",
      context: this.context,
      name: this.title,
    };
    const options = { stackPosition: "replaceCurrentAction" };
    return this.action.doAction(actionRequest, options);
  }

  // Hàm khởi tạo, lấy dữ liệu người dùng và tài khoản ngân hàng
  
  async initialize() {
    
    let data = await this.orm.searchRead(
      "res.users",
      [["id", "=", user.userId]],
      ["partner_id"]
    );
    this.state.resId = data[0].partner_id[0];

    data = await this.orm.searchRead(
      "t4tek.bank.account",
      [["partner_id", "=", this.state.resId]],
      ["acc_number", "balance_account"]
    );
    if (data.length === 0) {
      this.notification.add(
        _t("Bạn chưa có tài khoản ngân hàng. Vui lòng liên hệ quản trị viên."),
        { type: "danger" }
      );
      const paymentResult = await new Promise((resolve) => {
        setTimeout(() => {
          resolve(true);
        }, 2000);
      })
       window.location = "/web/session/logout";
      return;
    }
    
    this.state.balance_total = parseInt(data[0].balance_account).toLocaleString("vi-VN") + " VNĐ";
    this.state.acc_number = data[0].acc_number;
    // this.state.partnerId = data1[0].partner_ids[0];
    this.state.domain = [
       ["account_id.acc_number", "=", this.state.acc_number],
    ];

    data = await this.orm.searchRead(
      "bank.contact",
      [],
      ["bank_code"]
    );
   
    this.state.bankList = data;
    data = await this.orm.searchRead(
      "ir.model.data",
      [["name", "=", "form_view_res_partner"]],
      ["res_id"]
    );
     
    this.state.form_view_Id_partner = data[0].res_id;

    //  data = await this.orm.searchRead(
    //   "ir.model.data",
    //   [["name", "=", "list_view_transaction_report"]],
    //   ["res_id"]
    // );
    
    // this.state.list_view_Id_report = data[0].res_id;
  
    // data = await this.orm.searchRead(
    //   "ir.model.data",
    //   [["name", "=", "search_view_transaction_report"]],
    //   ["res_id"]
    // );
    // this.state.searchViewId = data[0].res_id;
   await this.loadViewData()
  }

  get viewProps() {
    const props = {
      ...this.baseViewProps,
      context: {},
      domain: [],
      resModel: "res.partner",
      // Ẩn res_id
      resId: this.state.resId,
      type: "form",
      viewId: this.state.form_view_Id_partner,
    };
    return props;
  }

  get viewPropsTreeViewReport() {
    if (!this.state.list_view_Id_report) return null;
    return {
        ...this.baseViewProps,
        context: {},
        resModel: "transaction.report",
        type: "list",
        domain: this.getDomainForType(this.state.transactionTab),
        viewId: this.state.list_view_Id_report,
        allowSelectors: true,
    };
}

  ////-----------start select tab---------------///////////// 
  async switchTab(type) {
    console.log(this.state.transactionTab)
    this.state.transactionTab = type;
    await this.loadViewData();
  }

  getDomainForType(type) {
        const domain = [["account_id.acc_number", "=", this.state.acc_number]];
              if (type !== "transaction_all") {
                domain.push(["transaction_type", "=", type]);
              }
              return domain;
  }

  async loadViewData() {
  if (!this.state.list_view_Id_report || !this.state.searchViewId) {
    const [listData, searchData] = await Promise.all([
      this.orm.searchRead(
        "ir.model.data",
        [["name", "=", "list_view_transaction_report"]],
        ["res_id"]
      ),
      this.orm.searchRead(
        "ir.model.data",
        [["name", "=", "search_view_transaction_report"]],
        ["res_id"]
      )
    ]);
    this.state.list_view_Id_report = listData[0].res_id;
    this.state.searchViewId = searchData[0].res_id;
  }
}


  
  async setFilter(filter) {
    console.log(filter);
  }
////-----------end select tab---------------///////////// 

  // Phương thức mở popup đổi điểm
  openDepositDialog() {
    let action = {
      type: "ir.actions.client",
      tag: "bank_server.action_transaction",
      target: "new",
      name: "NẠP TIỀN",
      params: {
        acc_number: this.state.acc_number,
        balance_total: this.state.balance_total,
        bankList: this.state.bankList,
        transactionType: "deposit",
        bus: this.env.bus,
      },
    };

    this.env.services.action.doAction(action, {
      onClose: () => {},
    });
  }

  openWithdrawalDialog() {
    let action = {
      type: "ir.actions.client",
      tag: "bank_server.action_transaction",
      target: "new",
      name: "RÚT TIỀN",
      params: {
        acc_number: this.state.acc_number,
        balance_total: this.state.balance_total,
        bankList: this.state.bankList,
        transactionType: "withdrawal",
        bus: this.env.bus,
      },
    };

    this.env.services.action.doAction(action, {
      onClose: () => {},
    });
  }

  openTransferOutDialog() {
    let action = {
      type: "ir.actions.client",
      tag: "bank_server.action_transaction",
      target: "new",
      name: "CHUYỂN TIỀN",
      params: {
        acc_number: this.state.acc_number,
        balance_total: this.state.balance_total,
        bankList: this.state.bankList,
        transactionType: "transfer_out",
        bus: this.env.bus,
      },
    };

    this.env.services.action.doAction(action, {
      onClose: () => {},
    });
  }

  // Render nội dung popup nhập điểm
  renderExchangePointsBody() {
    const bodyText = _t("Điểm Thưởng: %s Điểm", this.state.balance_total);
    return markup(
      _t(`
      <span>Điểm Thưởng: ${this.state.balance_total} Điểm</span>
      <div class="input-group input-group-sm">
        <span class="input-group-text">🎁</span>
        <input 
          type="number" 
          id="transactionMonney" 
          class="form-control form-control-sm" 
          placeholder="Nhập số điểm"
          min="0" 
          max="${this.state.balance_total}"
          oninput="()=>{}"
        />
        <span class="input-group-text">điểm</span>
      </div>
      <script>
        function onUpdateExchangePoints(){
        console.log(this)
        let a = document.getElementById("transactionMonney").value;
          console.log(a)
        } 
      </script>
  `)
    );
  }

  // Cập nhật số điểm muốn đổi
  onUpdateExchangePoints(event) {
    console.log(event.target.value);
    this.state.transactionMonney = parseInt(event.target.value) || 0;
  }

  // Đóng dialog
  closeDialog() {
    this.dialog.destroy();
  }

  // Xác nhận đổi điểm
  ActionTransation() {
    // Sử dụng ConfirmationDialog
    this.dialog.add(ConfirmationDialog, {
      body: _t(
        `CẢNH BÁO: Thao tác này KHÔNG THỂ HOÀN TÁC!\n\nBạn có chắc chắn muốn đổi ${this.state.transactionMonney} điểm không?`
      ),
      confirm: () => this.processTransaction(),
      cancel: () => {},
    });
  }

  // Xử lý đổi điểm
  async processTransaction() {
    mess = ''
     if(this.state.transactionType === 'deposit')
        mess = "Nạp tiền thành công !"
     else if(this.state.transactionType === 'withdrawal')
        mess = "Rút tiền thành công !"
     else if(this.state.transactionType === 'transfer_out')
        mess = "Chuyển tiền thành công !"


    try {
        this.notification.add(mess, {
        type: "success",
      });
   
      // Cập nhật lại số điểm
      this.state.reward_points_total -= this.state.transactionMonney;
    } catch (error) {
      this.notification.add("Có lỗi xảy ra khi giao dịch", {
        type: "danger",
      });
    }
  }
}

TransactionDashboard.template = "TransactionDashboard";
TransactionDashboard.components = { View };
TransactionDashboard.props = {};
registry
  .category("actions")
  .add("bank_server.transaction_dashboard", TransactionDashboard);
