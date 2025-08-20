from odoo import models, fields, api
import uuid
import logging
from odoo.http import request
import json
_logger = logging.getLogger(__name__)


class InvoiceReport(models.Model):
    _name = 'invoice.report'
    _description = 'Bill Payment Transaction'

    invoice_number = fields.Char(string='Mã hóa đơn', required=True)
    invoice_date = fields.Datetime(string='Ngày hóa đơn', default=fields.Datetime.now)
    seller_name = fields.Char(string='Người Bán', required=True)
    seller_account = fields.Char(string='Tài khoản Seller', required=True)
    seller_bank_code = fields.Char(string='Ngân hàng Seller', required=True)
    pos_key = fields.Char(string='Mã POS')
    pos_local = fields.Char(string='Điểm bán', required=True)
    pos_provide = fields.Char(string='Nhà cung cấp POS', required=True)
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

    #payment_time = fields.Datetime(string='Thời gian thanh toán')
    payment_report_ids = fields.One2many( 'transaction.report', 'invoice_id', string="Báo cáo giao dịch")
    transaction_id = fields.Char(string='Mã giao dịch hệ thống', readonly=True, copy=False)
    
    # payment_uuid = fields.Char(string='ID thanh toán', required=True)
    state = fields.Selection([
        ('draft', 'Khởi tạo'),
        ('done', 'Hoàn tất'),
        ('cancel', 'Hủy')
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
    
    @api.onchange('account_id')
    def _onchange_account_id(self):
        if self.account_id:
            self.partner_id = self.account_id.partner_id

    def set_done(self, transaction_report_id=None):
        for record in self:
            record.state = 'done'
            record.transaction_id = transaction_report_id    

    def set_cancel(self):
        for record in self:
            record.state = 'cancel'  # hoặc 'cancel' nếu bạn định nghĩa thêm trạng thái

    def payment_from_wallet(self):
        results = []
        draft_invoices = self.sudo().search([('state', '=', 'draft')])
        if draft_invoices:
           for rec in draft_invoices:
                result = rec.send_debt_paid()  # gọi hàm đã viết
                results.extend(result)  # append kết quả của từng record
       
           return results
    
    
    def send_debt_paid(self):
        results = []

        for rec in self.sudo():
            bank_contact = self.env['wallet.contact'].sudo().search([
                ('wallet_code', '=', rec.seller_bank_code)], limit=1)
            
            if not bank_contact or not bank_contact.api_url:
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": f"Không có URL API của ngân hàng [{rec.seller_bank_code}]"
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
                
            response, error = self.env['transaction.handle'].sudo()._send_request(
                method='POST',
                url=f'{bank_contact.api_url}api/invoice/sync',
                json_data=Data,
                headers={'Content-Type': 'application/json'},
            )
            _logger.info('---------------> response: %s', response)
            if error:
                results.append({
                    "invoice": rec.invoice_number,
                    "status": 'error',
                    "message": error,
                })
            else:
                status = response.get('result', {}).get('status')
                message = response.get('result', {}).get('message')
                
            if status == 'Success':
                invoice = response.get('result', {}).get('invoice')
                if invoice == 'draft':
                    # Gọi hàm _process_transaction từ controller xử lý giao dịch
                     # === 3. Gọi xử lý thanh toán ===
                   
                    transfer_data = {
                        'acc_number': self.acc_number,
                        'wallet': self.wallet,
                        'transferAccNumber': self.seller_account,
                        'transferWallet': self.seller_bank_code,
                        'transactionType': 'payment',
                        'invoiceNumber': self.invoice_number,
                        'monneyAmount': self.amount, }
                
                   
                    process_result = self.env['transaction.handle']._process_transaction(transfer_data)
                  
                    if process_result.get('status'):
                       rec.set_done(process_result.get('transactionUuid'))
                    results.append({
                        "status": process_result.get('status'),
                        "transactionUuid": process_result.get('transactionUuid'),
                        "message": process_result.get('message'),
                    })
                elif status == 'done':
                    transaction_id = response.get('result', {}).get('transaction_id')
                    payment_is = self.env['transaction.report'].sudo().search([
                        ('transaction_type', '=', 'payment'),
                        ('monney', '=', rec.amount),
                        ('transfer_uuid', '=', transaction_id)
                        ], limit=1)
                    if payment_is:
                            rec.set_done(transaction_id)
                            results.append({
                             "status": status,
                             "message": message,
                            })
                    else:
                        results.append({
                            "invoice": rec.invoice_number,
                            "status": 'error',
                            "message": f"Không tìm thấy giao dịch thanh toán với ID {transaction_id}",
                        })
                else:
                    results.append({
                        "invoice": rec.invoice_number,
                        "status": status,
                        "message": f"Thanh toán không thành công: {message}",
                    })
                

        return results
    
    def _add_general_invoice_information(self):
        self.ensure_one()
        invoice_data = {
            'invoiceNumber': str(self.invoice_number or ''),
            'invoiceDate': self.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if self.invoice_date else '',
            'POSLocal': str(self.pos_local or ''),
            'amount': float(self.amount or 0.0),
            'description': str(self.description or ''),
            'buyer': self._add_buyer_information(),
            'seller': self._add_seller_information(),
            
        }
        return invoice_data
    
    def _add_seller_information(self):
        self.ensure_one()
        buyer_data = {
            'sellerName': str(self.seller_name or ''),
            'sellerAccount': str(self.seller_account or ''),
            'sellerBank': str(self.seller_bank_code or ''),
        }
        return buyer_data

    
    def _add_buyer_information(self):
        self.ensure_one()
        seller_data = {
            'buyerName': str(self.partner_id.name if self.partner_id else ''),
            'buyerAccount': str(self.acc_number or ''),
            'buyerBank': str(self.wallet or ''),
        }
        return seller_data
    

    def action_show_invoice_report(self):
        domain = []
        # Nếu không phải quản lý, thì chỉ xem hóa đơn có liên kết với chính partner của user
        if not self.env.user.has_group('anypay_wallet.manager_wallet'):
            domain = [('partner_id', '=', self.env.user.partner_id.id)]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Hóa đơn thanh toán',
            'res_model': 'invoice.report',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {
                'search_default_filter_my_invoices': 1
            },
        }
