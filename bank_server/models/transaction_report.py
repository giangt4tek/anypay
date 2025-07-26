from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class TransactionReport(models.Model):
    _name = 'transaction.report'
    _description = 'Transaction Report'

    name = fields.Char(string='Transaction Reference', required=True, copy=False, readonly=True, default=lambda self: ('New'))
    
    account_id = fields.Many2one('t4tek.bank.account', string='Chủ tài khoản', help="Chủ tài khoản giao dịch")
    bank = fields.Char(string='Ngân hàng', required=True)
    
    transfer_acc_number = fields.Char(string='TK nhận/chuyển khoản', help="Tài khoản nhận tiền hoặc chuyển tiền")
    transfer_bank = fields.Char(string='Ngân hàng chuyển khoản')
    
    monney = fields.Float(string='Tiền', required=True)
    signed_monney = fields.Float(string="Số tiền", compute='_compute_signed_monney')
    transaction_code = fields.Char(string='Mã GD', required=True, copy=False, readonly=True, default=lambda self: ('New'))
    transaction_date = fields.Datetime(string='Thời gian GD', default=fields.Datetime.now)
    transaction_type = fields.Selection([
        ('deposit', 'Nạp tiền'),
        ('withdrawal', 'Rút tiền'),
        ('transfer_out', 'Chuyển khoản'),
        ('transfer_in', 'Nhận tiền'),
        ('payment', 'Thanh toán'),
        ('refund', 'Hoàn tiền'),
    ], string='Hình thức GD', required=True)
    transfer_uuid = fields.Char(string='ID giao dịch')
    note = fields.Text(string='Note')
    invoice_id = fields.Many2one('invoice.report', string="Hóa đơn liên quan")

    @api.model_create_multi
    def create(self, vals_list):
        result = []
        for vals in vals_list:
            last = self.search([], order='id desc', limit=1)
            last_code = last.transaction_code or ''
            
            if last_code and last_code.startswith(vals.get('transaction_type')):
                try:
                    number = int(last_code.split('/')[-1]) + 1
                except ValueError:
                    number = last.id + 1
            else:
                number = last.id + 1 if last else 1

            vals['transaction_code'] = f"{vals.get('transaction_type')}/{number:06d}"
            
            result.append(vals)
       
        return super().create(result)


    def _compute_signed_monney(self):
        for rec in self:
            if rec.transaction_type in ['withdrawal', 'transfer_out']:  # hoặc giá trị tương ứng
                rec.signed_monney = -rec.monney
            else:
                rec.signed_monney = rec.monney
       
   
    
    # partner_id = fields.Many2one(
    # 'res.partner',
    # string='Nhà Đầu Tư',
    # compute='_compute_partner_id',
    # store=True,
    # readonly=True,
    # required=True,)

    # @api.depends('account_id')
    # def _compute_partner_id(self):
    #     for rec in self:
    #         rec.partner_id = rec.account_id.partner_id

    # @api.model
    # def create(self, vals):
    #     if vals.get('name', 'New') == 'New':
    #         vals['name'] = self.env['ir.sequence'].next_by_code('bank_server.transaction_record') or 'New'
    #     return super(TransactionReport, self).create(vals)

