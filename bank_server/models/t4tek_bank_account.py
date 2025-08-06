from odoo import models, fields, api
from odoo.exceptions import UserError
import uuid
import random
import hashlib
import logging
_logger = logging.getLogger(__name__)


class T4tekBankAccount(models.Model):
    _name = 't4tek.bank.account'
    _description = 'Quản lý API cho từng tài khoản ngân hàng'

    #cccd_ids = fields.Many2one('res.partner', string="Căn cước công dân", required=True)
    #bank_id = fields.Many2one('res.partner.bank', string="Tài khoản ngân hàng", required=True)
    
    acc_number = fields.Char(string="Số tài khoản")
    client_key = fields.Char(string="client Key", readonly=True, copy=False)
    secret_key = fields.Char(string="Secret Key (SHA256)", readonly=True, copy=False)
    
    def generate_acc_number(self):
        for rec in self:
            existing_numbers = self.search([]).mapped('acc_number')
            while True:
                new_number = ''.join(random.choices('0123456789', k=11))
                if new_number not in existing_numbers:
                    break
            
            raw_key = str(uuid.uuid4())
            hashed_key = hashlib.sha256((raw_key).encode()).hexdigest()
            rec.client_key = hashed_key
            rec.acc_number = new_number
            raw_key = new_number[:5]+hashed_key+new_number[5:]
            rec.secret_key = hashlib.md5(raw_key.encode()).hexdigest()
         

          
    @api.model_create_multi
    def create(self, vals_list):
        partner_ids = [vals.get("partner_id") for vals in vals_list if vals.get("partner_id")]

        if partner_ids:
            # Tìm những partner_id đã có tài khoản
            existing = self.search([("partner_id", "in", partner_ids)])
            if existing:
                raise UserError("Một số người dùng đã có tài khoản ngân hàng.")

       # Không được thiếu return:
        return super().create(vals_list)

    # def write(self, vals):
    #     for rec in self:
    #        if 'secret_key' in vals and rec.secret_key:
    #           raise UserError("Không được chỉnh sửa Secret Key đã tồn tại.")
    #     return super().write(vals)


    # @api.constrains('acc_number')
    # def _check_unique_acc_number(self):
    #     for rec in self:
    #        if not rec.acc_number:
    #           raise UserError("Phải tạo số tài khoản trước khi lưu.")


    partner_id = fields.Many2one('res.partner', string="Thông tin người dùng", required=True)
    _sql_constraints = [
    ('partner_id_unique', 'unique(partner_id)', 'Người dùng này đã có tài khoản ngân hàng.')]
    is_active = fields.Boolean(string='Kích hoạt tài khoản', copy=False,
                               readonly=True, default=False)
    
    def set_is_active_account(self):
        for item in self:
            if item.acc_number or item.is_active == True:
                item.is_active = False
                raise UserError("Bắt buộc phải có số tài khoản (acc_number).")
            else:
                item.is_active = True
        return {}
    


    cccd_display = fields.Char(
        related='partner_id.cccd',
        string="Số CCCD",
        compute='_compute_cccd_display',
        store=False,
        readonly=True
    )

    vat_num_display = fields.Char(
        related='partner_id.vat',
        string="Mã số thuế",
        compute='_compute_vat_num_display',
        store=False,
        readonly=True
    )

    currency_id = fields.Many2one(
    "res.currency",
    string="Loại tiền tệ",
    required=True,
    default=lambda self: self.env.company.currency_id.id)

    balance_account = fields.Monetary(
    string="Số dư",
    currency_field="currency_id",
    compute="_compute_transaction_balance_total",
    default=0.0)

    def _compute_transaction_balance_total(self):
        for record in self:
            Transaction_reports = self.env['transaction.report'].search(
                [('account_id', '=', record.id)])
            balance_account = 0
            for transaction in Transaction_reports:
                if transaction.transaction_type in ['deposit' ,'transfer_in', 'payment']:
                    balance_account += transaction.monney
                elif transaction.transaction_type in ['withdrawal', 'transfer_out']:
                    balance_account -= transaction.monney
                else: return

            record.balance_account = balance_account


  