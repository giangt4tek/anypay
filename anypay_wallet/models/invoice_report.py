from odoo import models, fields, api
import uuid
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)
from ..controllers.wallet_api_controller import _send_request

class InvoiceReport(models.Model):
    _name = 'invoice.report'
    _description = 'Bill Payment Transaction'

    invoice_number = fields.Char(string='Mã hóa đơn', required=True)
    invoice_date = fields.Datetime(string='Thời gian tạo hóa đơn', default=fields.Datetime.now)
    seller_name = fields.Char(string='Người Bán', required=True)
    seller_account = fields.Char(string='Tài khoản Seller', required=True)
    seller_bank_code = fields.Char(string='Ngân hàng Seller', required=True)
    pos_local = fields.Char(string='Điểm bán')
    wallet = fields.Char(string='Ví điện tử', store=True, readonly=True)
    account_id = fields.Many2one('t4tek.wallet.account', string='Chủ tài khoản', help="Chủ tài khoản giao dịch")
    acc_number = fields.Char(
                 string="Số tài khoản",
                 related='account_id.acc_number',
                 store=True,
                 readonly=True)
    partner_id = fields.Many2one(
                'res.partner',
                string="Tên chủ khoản",
                related='account_id.partner_id',
                store=False,  # optional: lưu vào DB nếu cần tìm kiếm/sắp xếp
                readonly=True)
                
    amount = fields.Float(string='Số tiền', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id.id)

    description = fields.Text(string='Nội dung thanh toán')

    payment_time = fields.Datetime(string='Thời gian thanh toán')
    payment_report_ids = fields.One2many( 'transaction.report', 'invoice_id', string="Báo cáo giao dịch")
    transaction_id = fields.Char(string='Mã giao dịch hệ thống', readonly=True, copy=False)
    payment_uuid = fields.Char(string='ID thanh toán', required=True)
    state = fields.Selection([
        ('draft', 'Khởi tạo'),
        ('done', 'Hoàn tất'),
        ('error', 'Lỗi')
    ], default='draft', string='Trạng thái')

    note = fields.Text(string='Ghi chú nội bộ')

    @api.model_create_multi
    def create(self, vals_list):
        result = []
        for vals in vals_list:
           if not vals.get('transaction_id'):
              
              transactionUuid = str(uuid.uuid4())
              vals['transaction_id'] = transactionUuid
              result.append(vals)
        
        return super().create(result)
    
    @api.onchange('account_id')
    def _onchange_account_id(self):
        if self.account_id:
            self.partner_id = self.account_id.partner_id

    def set_done(self):
        for record in self:
            record.state = 'done'

    def set_cancel(self):
        for record in self:
            record.state = 'error'  # hoặc 'cancel' nếu bạn định nghĩa thêm trạng thái


    