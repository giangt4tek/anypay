from odoo import models, fields, api
import uuid
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)
from ..controllers.bank_api_controller import _send_request

class InvoiceReport(models.Model):
    _name = 'invoice.report'
    _description = 'Bill Payment Transaction'

    invoice_number = fields.Char(string='Mã hóa đơn', required=True)
    invoice_date = fields.Datetime(string='Thời gian tạo hóa đơn', default=fields.Datetime.now)
    buyer_name = fields.Char(string='Người thanh toán', required=True)
    buyer_account = fields.Char(string='Tài khoản thanh toán', required=True)
    buyer_bank_code = fields.Char(string='Ngân hàng thanh toán', required=True)
    pos_local = fields.Char(string='Điểm bán')
    
    account_id = fields.Many2one('t4tek.bank.account', string='Chủ tài khoản', help="Chủ tài khoản giao dịch")
    bank = fields.Char(string='Ngân hàng', store=True, readonly=True)
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


    def payment_from_wallet(self):
        draft_invoice = self.search([('state', '=', 'draft')])
        _logger.info('---------> hóa đơn chưa thanh toán %s', draft_invoice)
        for rec in draft_invoice:
            rec
        
  
    def send_debt_paid(self):
        results = []

        for rec in self.sudo():
            bank_contact = request.env['bank.contact'].sudo().search([
                ('bank_code', '=', self.buyer_bank_code)], limit=1)

            if not bank_contact or not bank_contact.api_url:
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": f"Không có URL API của ngân hàng [{self.buyer_bank_code}]"
                })
                continue

            Data = rec._add_general_invoice_information()
            response, error = _send_request(
                method='POST',
                url=f'{bank_contact.api_url}api/invoice/payment',
                json_data=Data,
                headers={'Content-Type': 'application/json'},
            )

            if error:
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": error,
                })
            else:
                results.append({
                    "status": response.get('result', {}).get('status'),
                    "message": response.get('result', {}).get('message'),
                })

        return results
    
    def _add_general_invoice_information(self):
        self.ensure_one()
        invoice_data = {
            'invoiceNumber': self.invoice_number,
            'invoiceDate': self.invoice_date.strftime('%Y-%m-%d %H:%M:%S'),
            'POSLocal': self.pos_local or '',
            'amount': self.amount,
            'description': self.description or '',
            'paymentUuid': self.payment_uuid,
            'buyer': self._add_buyer_information(),
            'seller': self._add_seller_information(),
            
        }
        return invoice_data
    
    def _add_buyer_information(self):
        self.ensure_one()
        buyer_data = {
            'buyerName': self.buyer_name,
            'buyerAccount': self.buyer_account,
            'buyerBankCode': self.buyer_bank_code,
           
        }
        return buyer_data
    
    def _add_seller_information(self):
        self.ensure_one()
        buyer_data = {
            'sellerName': self.partner_id,
            'sellerAccount': self.acc_number,
            'sellerBankCode': self.bank
           
        }
        return buyer_data