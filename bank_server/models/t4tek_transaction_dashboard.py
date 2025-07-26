from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError

class T4tekBankTransactionDashboard(models.Model):
    _name = 't4tek.transaction.dashboard'
    _description = 'Điều khiển giao dịch ngân hàng'
    

    name = fields.Char(string='Mã giao dịch', required=True, default=lambda self: self.env['ir.sequence'].next_by_code('t4tek.bank.transaction'))
    res_bank_account_id = fields.Many2one('t4tek.bank.account', string='Tài khoản ngân hàng', required=True)
    balance = fields.Float(
    string="Số dư hiện tại",
    help="Thay đổi tại đây sẽ cập nhật ngược lại vào tài khoản ngân hàng")

    transaction_type = fields.Selection([
        ('deposit', 'Nạp tiền'),
        ('withdraw', 'Rút tiền'),
        ('transfer', 'Chuyển khoản'),
    ], string='Loại giao dịch', required=True)
    amount = fields.Float(string='Số tiền', required=True)
    description = fields.Char(string='Mô tả')
    date = fields.Datetime(string='Ngày giao dịch', default=fields.Datetime.now)
    transfer_to_account = fields.Many2one('t4tek.bank.account', string='Tài khoản Nhận/Chuyển khoản')

    # --------------------------
    # Thực hiện giao dịch
    # --------------------------
    def action_execute_transaction(self):
        for rec in self:
            bank = rec.res_bank_account_id

            if rec.transaction_type == 'deposit':
                bank.balance += rec.amount

            elif rec.transaction_type == 'withdraw':
                if bank.balance < rec.amount:
                    raise UserError('Số dư không đủ để rút tiền')
                bank.balance -= rec.amount

            elif rec.transaction_type == 'transfer':
                if bank.balance < rec.amount:
                    raise UserError('Số dư không đủ để chuyển khoản')
                if not rec.transfer_to_account:
                    raise UserError('Bạn phải chọn tài khoản nhận chuyển khoản')

                # Trừ tiền người gửi
                bank.balance -= rec.amount
                # Cộng tiền người nhận
                rec.transfer_to_account.balance += rec.amount

                # Tạo lịch sử cho người nhận
                self.env['bank_server.transaction_record'].create({
                    'partner_id': rec.transfer_to_account.cccd_ids.id,
                    'transfer_acc_number': bank.acc_number,
                    'amount': rec.amount,
                    'transaction_code': rec.name,
                    'transaction_type': 'transfer',
                    'note': rec.description,
                })

            # Tạo lịch sử giao dịch cho người gửi / rút / nạp
            self.env['bank_server.transaction_record'].create({
                'partner_id': bank.cccd_ids.id,
                'transfer_acc_number': rec.transfer_to_account.acc_number if rec.transaction_type == 'transfer' else '',
                'amount': rec.amount,
                'transaction_code': rec.name,
                'transaction_type': rec.transaction_type,
                'note': rec.description,
            })
    
    # --------------------------
    # Đồng bộ từ bank -> dashboard
    # --------------------------
    @api.onchange('res_bank_account_id')
    def _onchange_sync_from_bank(self):
        for rec in self:
            rec.balance = rec.res_bank_account_id.balance if rec.res_bank_account_id else 0.0

    # --------------------------
    # Đồng bộ từ dashboard -> bank
    # --------------------------
    @api.onchange('balance')
    def _onchange_sync_to_bank(self):
        for rec in self:
            if rec.res_bank_account_id and rec.balance != rec.res_bank_account_id.balance:
                rec.res_bank_account_id.balance = rec.balance