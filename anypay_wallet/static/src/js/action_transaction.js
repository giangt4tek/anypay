/** @odoo-module **/
import {
  EventBus,
  Component,
  onWillStart,
  onMounted,
  markup,
  useState,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

export class ActionTransation extends Component {
  setup() {
    this.state = useState({
      balance_total: this.props.action.params.balance_total,
      transactionType: this.props.action.params.transactionType,
      acc_number: this.props.action.params.acc_number,
      confirmTransaction: false,
      submitButtonDisabled: true,
      partner_id: 0,
      monneyAmount : this.selectAmount.bind(this),
      packets: [100000, 200000, 500000, 1000000, 2000000, 5000000], // 💡 danh sách động
      walletList: this.props.action.params.walletList,
      transferWallet:''
    });
    this.selectAmount = this.selectAmount.bind(this); 
    this.notification = useService("notification");
    this.orm = useService("orm");
    this.bus = this.props.action.params.bus;

    onWillStart(async () => await this.initialize());

    onMounted(() => {
      const footer = document.querySelector("footer");
      if (footer != null) footer.classList.add("d-none");
      const formSheet = document.querySelector(".modal-dialog");
      formSheet.setAttribute(
        "style",
        "max-width:600px; margin-left: auto; margin-right: auto;"
      );

      // Lắng nghe sự kiện nhập điểm
      const MonneyAmountInput = document.getElementById("monneyAmount");
      MonneyAmountInput.addEventListener(
        "input",
        this.OnMonneyAmountChange.bind(this)
      );
    
      
      // Lắng nghe sự kiện checkbox
      const confirmCheckbox = document.getElementById("confirmTransaction");
      confirmCheckbox.addEventListener(
        "change",
        this.onConfirmCheckboxChange.bind(this)
      );
    });
  }

  selectAmount(value) {
    this.state.monneyAmount = parseInt(value);
    const input = document.querySelector('#monneyAmount');
    if (input) {
        input.value = Number(value).toLocaleString("vi-VN") + " VNĐ";
    }
  }
  
  onWalletChange(ev) {
    this.state.transferWallet = ev.target.value;

  } 


  async initialize() {
    let data = await this.orm.searchRead(
      "res.users",
      [["id", "=", user.userId]],
      ["partner_id"]
    );
    this.state.partner_id = data[0].partner_id[0];
    // data = await this.orm.searchRead(
    //   "loyalty.program",
    //   [["program_type", "=", "loyalty"]],
    //   ["rule_ids"]
    // );
    // let id_program_type = data[0].id;
    // data = await this.orm.searchRead(
    //   "loyalty.rule",
    //   [["id", "=", data[0].rule_ids[0]]],
    //   ["reward_point_amount"]
    // );
    // this.state.reward_point_amount = data[0].reward_point_amount;
    // data = await this.orm.searchRead(
    //   "loyalty.card",
    //   [["partner_id", "=", this.state.partner_id]],
    //   ["points"]
    // );
   
    // this.state.reward_loyalty = data[0].points;
    // this.state.reward_point_amount_exchange = this.state.reward_loyalty;
  }

  // Kiểm tra và cập nhật điểm nhập vào
  OnMonneyAmountChange(ev) {
    let raw_value = ev.target.value.replace(/\D/g, ''); // chỉ lấy số
    if (!raw_value) {
        ev.target.value = '';
        return;
    }
   
    debugger;
    const inputValue = parseInt(raw_value) || 0;
    // Kiểm tra điều kiện nhập điểm
    if (inputValue < 0) {
      ev.target.value = 0;
      this.state.monneyAmount = 0;
      this.showNotification("Số điểm không được âm", "Lỗi", "danger");
    } else {
      let formatted = Number(inputValue).toLocaleString('vi-VN')  + " VNĐ";
      ev.target.value = formatted;
      this.state.monneyAmount = inputValue;
      // this.state.reward_point_amount_exchange =
      //   inputValue * this.state.reward_point_amount + this.state.reward_loyalty;
    }

    // Cập nhật trạng thái nút submit
    this.updateSubmitButton();
  }

  // Xử lý sự kiện checkbox xác nhận
  onConfirmCheckboxChange(ev) {
    this.state.confirmTransaction = ev.target.checked;
    this.updateSubmitButton();
  }

  // Cập nhật trạng thái nút submit
  updateSubmitButton() {
    const submitButton = document.querySelector('button[type="submit"]');
    const confirmCheckbox = document.getElementById("confirmTransaction");

    // Nút chỉ được bật khi đủ điều kiện
    this.state.submitButtonDisabled = !(
      this.state.monneyAmount > 0 &&
      confirmCheckbox.checked
    );
    submitButton.disabled = this.state.submitButtonDisabled;
  }

  // Hiển thị thông báo
  showNotification(content, title, type) {
    const notification = this.notification;
    notification.add(content, {
      title: title,
      type: type,
      className: "p-4",
    });
  }

  // Xử lý khi submit form
  async onSubmit(ev) {
    ev.preventDefault();
    // const submitButton = document.getElementsByClassName("o_dialog");
    // if (submitButton.length > 0) submitButton[0].classList.add("d-none");
    // Kiểm tra lại các điều kiện
   
    if (this.state.submitButtonDisabled) {
      return;
    }
    try {
      // Gọi RPC để xử lý đổi điểm
      if (this.state.monneyAmount <= 0) {
        this.showNotification(
          "Bạn chưa nhập số tiền",
          "Lỗi",
          "danger"
        );
        return;
      }
      this.transfer_number = ''
      if (this.state.transactionType === 'transfer_out')
      {
         this.transfer_number = document.querySelector('#accountNumber') ? document.querySelector('#accountNumber').value : '';
         if (this.transfer_number && this.transfer_number.trim() == '') 
         {
              this.showNotification(
               "Bạn chưa nhập tài khoản người nhận",
               "Cảnh báo",
               "danger"
             );
             return;
         }

         if (this.state.transferWallet && this.state.transferWallet.trim() == '') 
         {
              this.showNotification(
               "Bạn chưa chọn Ví AnyPay",
               "Cảnh báo",
               "danger"
             );
              return;
         }


      }
         
      const result = await rpc("/api/transaction", {
        monneyAmount: this.state.monneyAmount,
        partner_id: this.state.partner_id,
        user_id: user.userId,
        transactionType: this.state.transactionType,
        acc_number: this.state.acc_number,
        transferAccNumber: this.transfer_number,
        transferWallet: this.state.transferWallet,
        transactionUuid: ''
      });
      
      let mess = '';
      if (this.state.transactionType === 'deposit')
        mess = "Nạp tiền ";
      else if (this.state.transactionType === 'withdrawal')
        mess = "Rút tiền ";
      else if (this.state.transactionType === 'transfer_out')
        mess = "Chuyển tiền ";
      debugger;
      if (result.status) {
          if(this.state.transactionType === "deposit")
             {this.state.balance_total = this.state.balance_total + this.state.monneyAmount;}
          else if (this.state.transactionType === "withdrawal" || this.state.transactionType === "transfer_out") {
              this.state.balance_total = this.state.balance_total - this.state.monneyAmount;}
        
        this.bus.trigger("update_balance_total", {
          transactionType: this.state.transactionType,
          monneyAmount: this.state.monneyAmount,
        });
        
        const dialog = document.querySelector(".o_dialog");
        if (dialog != null) dialog.classList.add("d-none");
           {  
           this.showNotification(
             mess,
             "Thành Công",
             "success"
           );
          }
          
        // Đóng modal hoặc chuyển hướng
      } else {
        this.showNotification(
          result.message || (mess + " không thành công"),
          "Lỗi",
          "danger"
        );
      }
    } catch (error) {
      this.showNotification("Có lỗi xảy ra khi đổi điểm", "Lỗi", "danger");
    }
  }
}


ActionTransation.template = "anypay_wallet.action_transaction";
ActionTransation.props = { ...standardFieldProps };
registry
  .category("actions")
  .add("anypay_wallet.action_transaction", ActionTransation);
