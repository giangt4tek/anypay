from odoo import models, fields, api
import uuid
import logging
import json
from odoo.http import request
_logger = logging.getLogger(__name__)
from ..controllers.api_controller import _send_request

class InvoiceReport(models.Model):
    _name = 'invoice.report'
    _description = 'Bill Payment Transaction'

    invoice_number = fields.Char(string='Mã hóa đơn', required=True)
    invoice_date = fields.Datetime(string='Thời gian tạo hóa đơn', default=fields.Datetime.now)
    
    buyer_account = fields.Char(string='Tài khoản thanh toán', required=True)
    buyer_wallet = fields.Char(string='Ngân hàng thanh toán', required=True)

    pos_id = fields.Many2one('pos.category', string='Điểm bán', help="Điểm bán hàng liên kết với hóa đơn này")
                
    amount = fields.Float(string='Số tiền', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id.id)

    description = fields.Text(string='Nội dung thanh toán')

    payment_time = fields.Datetime(string='Thời gian thanh toán')
    transaction_id = fields.Char(string='Mã giao dịch hệ thống', readonly=True, copy=False)
    payment_uuid = fields.Char(string='ID thanh toán', required=True)
    state = fields.Selection([
        ('draft', 'Khởi tạo'),
        ('done', 'Hoàn tất'),
        ('cancel', 'Hủy bỏ'),
        ('error', 'Lỗi')
    ], default='draft', string='Trạng thái')

    note = fields.Text(string='Ghi chú nội bộ')

    # @api.model_create_multi
    # def create(self, vals_list):
    #     result = []
    #     for vals in vals_list:
    #        if not vals.get('transaction_id'):
              
    #           transactionUuid = str(uuid.uuid4())
    #           vals['transaction_id'] = transactionUuid
    #           result.append(vals)
        
    #     return super().create(result)
    
    # @api.onchange('account_id')
    # def _onchange_account_id(self):
    #     if self.account_id:
    #         self.partner_id = self.account_id.partner_id

    def set_done(self, transaction_report_id=None):
        for record in self:
            record.state = 'done'
            record.transaction_id = transaction_report_id  

    def set_cancel(self):
        for record in self:
            record.state = 'cancel'  # hoặc 'cancel' nếu bạn định nghĩa thêm trạng thái


    def invoice_sync(self):
        results = []
        draft_invoices = self.sudo().search([('state', '=', 'draft')])
        if draft_invoices:
           for rec in draft_invoices:
                result = rec.send_invoice()  # gọi hàm đã viết
                results.extend(result)  # append kết quả của từng record
        
        return results
        
  
    def send_invoice(self):
        results = []
        
        for rec in self.sudo():
            wallet_contact = self.env['wallet.contact'].sudo().search([
                ('wallet_code', '=', rec.buyer_wallet)], limit=1)
          
            if not wallet_contact or not wallet_contact.api_url:
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": f"Không có URL API của ngân hàng [{rec.buyer_wallet}]"
                })
                continue
         
            Data = rec._add_general_invoice_information()
          
            try:
                json.dumps(Data)
            except TypeError as e:
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": f"Dữ liệu JSON không hợp lệ: {e}"
                })
                continue
          
            response, error = _send_request(
                method='POST',
                url=f'{wallet_contact.api_url}api/invoice/payment',
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
                #transaction_id = response.get('result', {}).get('transaction_id')
               
                if status == 'Success':
                    rec.set_done(response.get('result', {}).get('transactionUuid'))
                    results.append({
                        "status": status,
                        "message": message,
                    })
                elif status == 'notify':
                    rec.set_done(response.get('result', {}).get('transactionUuid'))
                    results.append({
                        "status": status,
                        "message": message,
                    })
                else:
                    results.append({
                        "invoice": rec.invoice_number,
                        "status": 'error',
                        "message": f"Trạng thái không thành công: {status}, {message}",
                    })

        return results
    
    def _add_general_invoice_information(self):
        self.ensure_one()
        invoice_data = {
            'invoiceNumber': str(self.invoice_number or ''),
            'invoiceDate': self.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if self.invoice_date else '',
            'POSLocal': str(self.pos_id.pos_name or ''),
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
            'buyerAccount': str(self.buyer_account or ''),
            'buyerBank': str(self.buyer_wallet or ''),
        }
        return buyer_data

    
    def _add_seller_information(self):
        self.ensure_one()
        seller_data = {
            'sellerName': str(self.pos_id.pos_user or ''),
            'sellerAccount': str(self.pos_id.bank_acc or ''),
            'sellerBank': str(self.pos_id.bank_code or ''),
        }
        return seller_data
