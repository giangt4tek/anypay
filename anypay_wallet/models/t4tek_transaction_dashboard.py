from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError

class T4tekWalletTransactionDashboard(models.Model):
    _name = 't4tek.transaction.dashboard'
    _description = 'Điều khiển giao dịch Ví AnyPay'
    

    name = fields.Char(string='Mã giao dịch', required=True, default=lambda self: self.env['ir.sequence'].next_by_code('t4tek.wallet.transaction'))
    res_wallet_account_id = fields.Many2one('t4tek.wallet.account', string='Tài khoản Ví AnyPay', required=True)
    balance = fields.Float(
    string="Số dư hiện tại",
    help="Thay đổi tại đây sẽ cập nhật ngược lại vào tài khoản Ví AnyPay")

    transaction_type = fields.Selection([
        ('deposit', 'Nạp tiền'),
        ('withdraw', 'Rút tiền'),
        ('transfer', 'Chuyển khoản'),
    ], string='Loại giao dịch', required=True)
    amount = fields.Float(string='Số tiền', required=True)
    description = fields.Char(string='Mô tả')
    date = fields.Datetime(string='Ngày giao dịch', default=fields.Datetime.now)
    transfer_to_account = fields.Many2one('t4tek.wallet.account', string='Tài khoản Nhận/Chuyển khoản')

    # --------------------------
    # Thực hiện giao dịch
    # --------------------------
    def action_execute_transaction(self):
        for rec in self:
            wallet = rec.res_wallet_account_id

            if rec.transaction_type == 'deposit':
                wallet.balance += rec.amount

            elif rec.transaction_type == 'withdraw':
                if wallet.balance < rec.amount:
                    raise UserError('Số dư không đủ để rút tiền')
                wallet.balance -= rec.amount

            elif rec.transaction_type == 'transfer':
                if wallet.balance < rec.amount:
                    raise UserError('Số dư không đủ để chuyển khoản')
                if not rec.transfer_to_account:
                    raise UserError('Bạn phải chọn tài khoản nhận chuyển khoản')

                # Trừ tiền người gửi
                wallet.balance -= rec.amount
                # Cộng tiền người nhận
                rec.transfer_to_account.balance += rec.amount

                # Tạo lịch sử cho người nhận
                self.env['anypay_wallet.transaction_record'].create({
                    'partner_id': rec.transfer_to_account.cccd_ids.id,
                    'transfer_acc_number': wallet.acc_number,
                    'amount': rec.amount,
                    'transaction_code': rec.name,
                    'transaction_type': 'transfer',
                    'note': rec.description,
                })

            # Tạo lịch sử giao dịch cho người gửi / rút / nạp
            self.env['anypay_wallet.transaction_record'].create({
                'partner_id': wallet.cccd_ids.id,
                'transfer_acc_number': rec.transfer_to_account.acc_number if rec.transaction_type == 'transfer' else '',
                'amount': rec.amount,
                'transaction_code': rec.name,
                'transaction_type': rec.transaction_type,
                'note': rec.description,
            })
    
    # --------------------------
    # Đồng bộ từ wallet -> dashboard
    # --------------------------
    @api.onchange('res_wallet_account_id')
    def _onchange_sync_from_wallet(self):
        for rec in self:
            rec.balance = rec.res_wallet_account_id.balance if rec.res_wallet_account_id else 0.0

    # --------------------------
    # Đồng bộ từ dashboard -> wallet
    # --------------------------
    @api.onchange('balance')
    def _onchange_sync_to_wallet(self):
        for rec in self:
            if rec.res_wallet_account_id and rec.balance != rec.res_wallet_account_id.balance:
                rec.res_wallet_account_id.balance = rec.balance