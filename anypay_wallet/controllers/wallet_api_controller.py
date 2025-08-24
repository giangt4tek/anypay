from odoo import _, api, http, fields
import json
import requests
from odoo.http import request
from odoo.http import Response
from requests import RequestException
import hashlib
import uuid
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from dateutil.relativedelta import relativedelta
_TIMEOUT = 60 
_API_URL = ''
_WALLET = 'VMONNEY'

class _Get_WalletApiController(http.Controller):
    _name  = 'wallet.api.controller'
      
    @http.route('/api/token', type='http', auth='none', methods=['POST'], csrf=False)
    def get_api_key(self, **kwargs):
        data = request.httprequest.form
        acc_number = data.get('partner_code')
        client_key = data.get('client_key')
        ip = request.httprequest.remote_addr
        
        if not acc_number or not client_key:
            return {'error': 'Thiếu partner_code hoặc api_key'}

        # Hash secret từ client
        raw_key = acc_number[:5]+client_key+acc_number[5:]
        secret_key = hashlib.md5(raw_key.encode()).hexdigest()

        # Tìm partner theo số tài khoản + secret mã hóa
        partner = request.env['t4tek.wallet.account'].sudo().search([
            ('acc_number', '=', acc_number),
            ('secret_key', '=', secret_key)
        ], limit=1)
      
        if not partner:
            return Response(
                json.dumps({'error': 'Yêu cầu token thất bại không tìm thấy tài khoản'}),
                content_type='application/json'
            )
       
        # Xóa API key đã hết hạn (dọn dẹp)
        request.env['api.key'].sudo().search([
            ('t4tek_acc', '=', partner.id),
            ('expired_at', '<=', fields.Datetime.now())
        ]).unlink()
        
        # Nếu đã có key còn hạn → trả lại
        existing_key = request.env['api.key'].sudo().search([
            ('t4tek_acc', '=', partner.id),
            ('expired_at', '>', fields.Datetime.now())
        ], limit=1)

        if existing_key:
            existing_key.sudo().unlink()  # Xóa key cũ

        new_key = request.env['api.key'].sudo().create({
            't4tek_acc': partner.id,
            'scope': 'read',
            'expired_at': fields.Datetime.now() + relativedelta(minutes=15),  # 15 phút
            #'user_id': default_user.id,  # Bắt buộc phải có dòng này
        })

        return Response(
                json.dumps({
                    'api_key': new_key.name,
                    'expires_at': new_key.expired_at.isoformat()
                }),
                content_type='application/json')
 
    @http.route('/api/transaction', type='json', auth='user', methods=["POST"], csrf=False)
    def action_transaction(self, **kw):
       try:
            if kw:
               data = kw
               if not data.get('wallet'): data['wallet'] = _WALLET
            else: '', 'Không nhận được dữ liệu'
       
            result = request.env["transaction.handle"]._process_transaction(data)
            
            return result
       
       except Exception as e:
            return {
                "status": "error",
                "message": f"Lỗi hệ thống: {str(e)}"
            }
  
    @http.route('/api/transaction/transfer/in', type='json', auth='none', methods=["POST"], csrf=False)
    def _action_transfer_create(self, **kwargs):
        
        raw_body = request.httprequest.get_data(as_text=True)
        data = json.loads(raw_body)
        required_fields = ['transactionType', 'transactionUuid', 'monneyAmount', 'acc_number', 'transferAccNumber', 'wallet', 'transferwallet']
        for name in required_fields:
            if not data.get(name):
                return {
                    'status': 'error',
                    'message': 'Trường [{name}] không có dữ liệu'
                    }
                  
        result = request.env["transaction.handle"]._process_transaction(data)
        
        if result.get('status'): 
            return {
                    "status": 'Success',
                    "message": 'Chuyển khoản thành công'
                }
        else:
            return {
                'status': 'error',
                'message': 'Chuyển khoản không thành công.',
                'Fail': result.message
            }
            
    @http.route('/api/invoice/sync', type='json', auth='none', methods=["POST"], csrf=False)
    def create_invoice_debit(self, **post):
        raw_body = request.httprequest.get_data(as_text=True)
        data = json.loads(raw_body)
        header = request.httprequest.headers
        invoices = data.get("invoices", [])
        card_id = header.get('id')
        
        results = []
        for inv in invoices:
            inv.update({'buyerAccount': card_id})
            inv.update({'buyerWallet': _WALLET})
            inv_is = request.env["transaction.handle"].pos_system_sync(inv)
            
            if inv_is.get('status') == False:
               _logger.info(f"---> Hóa đơn lỗi: {inv} ")
            # invoice_number = inv.get("invoiceNumber")
            # invoice_date = inv.get("invoiceDate")
            # pos_key = inv.get("secretKey")
            # pos_provide = inv.get("posProvide")
            # amount = inv.get("amount")
            
        return "Ok, đã chạy xong"

        # if not (pos_key and pos_provide):
        #     _logger.info(f'Dữ liệu hóa đơn: {[data.get('invoiceNumber', '')]} trong thẻ không có Key hoặc Provide của POS')
        
        # Key = {'posKey': pos_key}
        

            # pos_contact = self.env['wallet.contact'].sudo().search([
            #     ('wallet_code', '=', rec.seller_bank_code)], limit=1)
            
            # if not bank_contact or not bank_contact.api_url:
            #     results.append({
            #         "invoice": rec.invoice_number,
            #         "status": 'error',
            #         "message": f"Không có URL API của ngân hàng [{rec.seller_bank_code}]"
            #     })
        
        
    @http.route('/api/invoice/payment', type='json', auth='none', methods=["POST"], csrf=False)
    def invoice_payment(self, **post):
        try:
            raw_body = request.httprequest.get_data(as_text=True)
            data = json.loads(raw_body)
            # === 1. Tách dữ liệu ===
            buyer_info = data['buyer'] if isinstance(data.get('buyer'), dict) else None
            seller_info = data['seller'] if isinstance(data.get('seller'), dict) else None
            if not buyer_info or not seller_info:
                return {
                    'status': 'error',
                    'message': 'Thiếu thông tin người mua hoặc người bán.'
                }

            invoice_info = {
                'acc_number': buyer_info.get('buyerAccount'),
                'wallet': buyer_info.get('buyerWallet'),
                'invoiceNumber': data.get('invoiceNumber'),
                'invoiceDate': data.get('invoiceDate'),
                'POSLocal': data.get('POSLocal'),
                'POSProvide' : data.get('POSProvide'),
                'amount': data.get('amount'),
                'description': data.get('description') or '',
                'sellerName': seller_info.get('sellerName'),
                'sellerAccount': seller_info.get('sellerAccount'),
                'sellerBank': seller_info.get('sellerBank'),
            }

            # === 2. Ghi nhận hóa đơn ===
            
            invCreate = request.env["transaction.handle"].create_invoice(invoice_info)
           
            if invCreate.get('status') == False and invCreate.get('is_ivoice') == False:
                return {
                    'status': 'error',
                    'message': invCreate['message'],}
            
            if invCreate.get('invoice_state') == 'done' and invCreate.get('is_ivoice') == True:
                
                transfer_is = request.env['transaction.report'].sudo().search([
                    ('transaction_type', '=', 'payment'),
                    ('transfer_uuid', '=', invCreate.get('transaction_id'))
                ], limit=1)

                if transfer_is:
                    return {
                        'status': 'notify',
                        'message': 'Hóa đơn đã được thanh toán trước đó.',
                        'transactionUuid': invCreate.get('transaction_id')
                    }
            
            # Lấy trạng thái hóa đơn nếu cần
            if invCreate.get('is_ivoice') == True and invCreate.get('invoice_state') == 'draft': 
            # === 3. Gọi xử lý thanh toán ===
                invoice_record = request.env['invoice.report'].sudo().search([
                        ('invoice_number', '=', invoice_info['invoiceNumber']),
                        ('pos_provide' , '=' , invoice_info['POSProvide']),
                        ('pos_local' , '=' , invoice_info['POSLocal']),
                        ('acc_number', '=', invoice_info['acc_number']),
                    ], limit=1)
                
                if invoice_record: 
                    # Gọi hàm send_debt_paid để xử lý thanh toán
                   result = invoice_record.send_debt_paid()
                   # Nếu là list thì lấy phần tử đầu tiên
                   if isinstance(result, list) and result:
                       result_data = result[0]
                   else:
                       result_data = {}
                   
                   raw_status = result_data.get('status', False)
                   status_str = 'Success' if raw_status is True else ('notify' if raw_status == 'notify' else 'error')

                   return {
                       "status": status_str,
                       "transactionUuid": result_data.get('transactionUuid'),
                       "message": result_data.get('message', 'Không rõ kết quả')
                   }
                #    return {
                #         "status": 'Success',
                #         "transactionUuid": result.get('transactionUuid'),
                #         "message": 'Thanh toán thành công'
                #     }
                # transfer_data = {
                #     'acc_number': buyer_info.get('buyerAccount'),
                #     'wallet': buyer_info.get('buyerBank'),
                #     'transferAccNumber': seller_info.get('sellerAccount'),
                #     'transferWallet': seller_info.get('sellerBank'),
                #     'transactionType': 'payment',
                #     'monneyAmount': data.get('amount'), 
                #     'invoiceNumber': data.get('invoiceNumber'),
                
                # result = request.env["transaction.handle"]._process_transaction(transfer_data)
                #if result.get('status'):
                    # === 4. Cập nhật trạng thái hóa đơn ===
                    # invoice_record = request.env['invoice.report'].sudo().search([
                    #     ('invoice_number', '=', invoice_info['invoiceNumber']),
                    #     ('acc_number', '=', invoice_info['acc_number']),
                    # ], limit=1)
                   
                    #invoice_record.set_done(result.get('transactionUuid'))  # Cập nhật trạng thái hóa đơn thành 'done'
            
                    # return {
                    #     "status": 'Success',
                    #     "transactionUuid": result.get('transactionUuid'),
                    #     "message": 'Thanh toán thành công'
                    # }
                else:
                    return {
                        "status": "error",
                        "message": f"Thanh toán thất bại",
                        "fail": result.get('message')
                    }
            if invCreate.get('invoice_state') == 'done':
                return {
                    "status": "error",
                    "message": "Hóa đơn đã được thanh toán trước đó."
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Lỗi hệ thống: {str(e)}"
            }
        