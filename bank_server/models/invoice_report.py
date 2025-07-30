from odoo import models, fields, api
import uuid
import logging
from odoo.http import request
import json
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


    def payment_draft_invoice(self):
        results = []
        draft_invoices = self.sudo().search([('state', '=', 'draft')])
       
        for rec in draft_invoices:
             result = rec.send_debt_paid()  # gọi hàm đã viết
             results.extend(result)  # append kết quả của từng record
     
        return results
        
  
    def send_debt_paid(self):
        results = []

        for rec in self.sudo():
            bank_contact = self.env['bank.contact'].sudo().search([
                ('bank_code', '=', rec.buyer_bank_code)], limit=1)
            
            if not bank_contact or not bank_contact.api_url:
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": f"Không có URL API của ngân hàng [{rec.buyer_bank_code}]"
                })
                continue
           
            Data = rec._add_general_invoice_information()
            
            try:
                json.dumps(Data)
            except TypeError as e:
                _logger.error("Payload JSON không hợp lệ: %s", e)
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": f"Dữ liệu JSON không hợp lệ: {e}"
                })
                continue
           
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
                status = response.get('result', {}).get('status')
                message = response.get('result', {}).get('message')
                results.append({
                    "status": status,
                    "message": message,
                })
                if status == 'Success':
                    rec.set_done()

        return results
    
    def _add_general_invoice_information(self):
        self.ensure_one()
        invoice_data = {
            'invoiceNumber': str(self.invoice_number or ''),
            'invoiceDate': self.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if self.invoice_date else '',
            'POSLocal': str(self.pos_local or ''),
            'amount': float(self.amount or 0.0),
            'description': str(self.description or ''),
            'paymentUuid': str(self.payment_uuid or ''),
            'buyer': self._add_buyer_information(),
            'seller': self._add_seller_information(),
            
        }
        return invoice_data
    
    def _add_buyer_information(self):
        self.ensure_one()
        buyer_data = {
            'buyerName': str(self.buyer_name or ''),
            'buyerAccount': str(self.buyer_account or ''),
            'buyerBank': str(self.buyer_bank_code or ''),
        }
        return buyer_data

    
    def _add_seller_information(self):
        self.ensure_one()
        seller_data = {
            'sellerName': str(self.partner_id.name if self.partner_id else ''),
            'sellerAccount': str(self.acc_number or ''),
            'sellerBank': str(self.bank or ''),
        }
        return seller_data
