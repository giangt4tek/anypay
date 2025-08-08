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
_BANK = 'ACB'
_TRANSFER_BANK = ''

def _send_request(method, url, json_data=None, form_data=None, params=None, headers=None, cookies=None):
    """ Send a request to the API based on the given parameters. In case of errors, the error message is returned. """
    try:
        if json_data:
            resp = requests.request(
                method,
                url,
                json=json_data,
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=_TIMEOUT
            )
        elif form_data:
            resp = requests.request(
                method,
                url,
                data=form_data,  # Đây là điểm quan trọng cho x-www-form-urlencoded
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=_TIMEOUT
            )
        else:
            resp = requests.request(
                method,
                url,
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=_TIMEOUT
            )
        
        resp_json = resp.json()
        error = None
        
        if resp_json.get('code') or resp_json.get('error'):
            data = resp_json.get('data') or resp_json.get('error')
            error = _('Error when contacting e_invoice: %s.', data)
        return resp_json, error
    except (RequestException, ValueError) as err:
        return {}, _('Something went wrong, please try again later: %s', err)


class _Get_BankApiController(http.Controller):
    _name  = 'api.controller'

    def send_transfer_request(self, Data, contact_bank):
        
        bank_contact = request.env['wallet.contact'].sudo().search([
            ('wallet_code', '=', contact_bank)], limit=1)
        
        if not bank_contact.api_url:
            code = bank_contact.get('wallet_code')
            return {
                "status": 'error',
                "message": 'Không có URL API của ngân hàng [{code}] ',
            }
        
        response, error = _send_request(
            method='POST',
            url=f'{bank_contact.api_url}api/transaction/transfer/in',
            json_data=Data,
            headers={'Content-Type': 'application/json'},
        )
        if error: 
            return {
                "status": 'error',
                "message": error,
            }
        else:    
            return {
                "status": response.get('result', {}).get('status'),
                "message": response.get('result', {}).get('message'),
                    }
        
    @http.route('/pos/token', type='http', auth='none', methods=['POST'], csrf=False)
    def get_api_key(self, **kwargs):
        data = request.httprequest.form
        client_key = data.get('client_key')
      
        #ip = request.httprequest.remote_addr
        
        if not client_key:
            return {'error': 'Thiếu key xác thực client_key'}

        # Tìm POS theo client_key được cấp
        POS = request.env['pos.category'].sudo().search([
            ('client_key', '=', client_key)
        ], limit=1)
      
        if not POS:
            return Response(
                json.dumps({'error': 'Yêu cầu token thất bại không định danh của POS'}),
                content_type='application/json'
            )
      
        # Xóa API key đã hết hạn (dọn dẹp)
        request.env['api.key'].sudo().search([
            ('pos_id', '=', POS.id),
            ('expired_at', '<=', fields.Datetime.now())
        ]).unlink()
       
        # Nếu đã có key còn hạn → trả lại
        existing_key = request.env['api.key'].sudo().search([
            ('pos_id', '=', POS.id),
            ('expired_at', '>', fields.Datetime.now() + relativedelta(minutes=15))
        ], limit=1)
       
        if existing_key:
            return Response(
                json.dumps({
                    'api_key': existing_key.token,
                    'expires_at': existing_key.expired_at.isoformat()
                }),
                content_type='application/json')
        
        if existing_key:
            existing_key.sudo().unlink()  # Xóa key cũ
       
        new_key = request.env['api.key'].sudo().create({
            'pos_id': POS.id,
            'scope': 'read',
            'expired_at': fields.Datetime.now() + relativedelta(minutes=60),  # 1h
            #'user_id': default_user.id,  # Bắt buộc phải có dòng này
        })
       
        return Response(
                json.dumps({
                    'api_key': new_key.token,
                    'expires_at': new_key.expired_at.isoformat()
                }),
                content_type='application/json')
 
      
    @http.route('/api/invoice/sync', type='json', auth='none', methods=["POST"], csrf=False)
    def create_invoice_sync(self, **post):
        
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return {'status': 'error', 'message': _('Thiếu hoặc sai định dạng Authorization header')}
    
        token = auth_header.replace("Bearer ", "").strip().strip('"').rstrip('/')
       
        raw_body = request.httprequest.get_data(as_text=True)
        data = json.loads(raw_body)
        auth_token = request.env['api.key'].sudo().search([('token', '=', token)], limit=1)
       
        if (not auth_token or auth_token.expired_at <= fields.Datetime.now()):
            return {
                    'status': 'error',
                    'message': 'Token không tồn tại'}
        else:
            data['pos'] = auth_token.pos_id if auth_token.pos_id else None
        # Kiểm tra các trường bắt buộc
            required_fields = [
                'invoiceNumber', 'invoiceDate', 
                'buyerAccount', 'buyerWallet',
                'amount', 'paymentUuid', 'pos'
            ]
            for name in required_fields:
                if not data.get(name):
                    return {
                         'status': False,
                         'message': f'Trường [{name}] không có dữ liệu'  }
      
        invCreate = self.create_invoice(data)    
        if invCreate['status']: 
            return {
                'status': 'success',
                'message': 'Hóa đơn đã được ghi nhận.'
            }
        else:
            return {
                    'status': 'error',
                    'message': 'Hóa đơn không được ghi nhận.',
                    'Fail': invCreate['message']
                }   
        
   
# -------------------------------------- Initialization Handl -------------------------------------------

    def create_invoice(self, data):
        try:
            invocie_is = request.env['invoice.report'].sudo().search([
                ('invoice_number', '=', data['invoiceNumber']),
                 ('pos_id', '=', data['pos'].id),
                 ('payment_uuid', '=', data['paymentUuid'])], limit=1)
          
            if invocie_is:
                return {
                    'status': False,
                    'is_ivoice': True,
                    'invoice_state': invocie_is.state,
                    'message': 'Hóa đơn đã tồn tại.'
                }
          
            # Tạo hóa đơn mới
            invoice = request.env['invoice.report'].sudo().create({
                'invoice_number': data['invoiceNumber'],
                'invoice_date': data['invoiceDate'],
                'pos_id': data['pos'].id,
                'buyer_account': data['buyerAccount'],
                'buyer_wallet':data['buyerWallet'],
                'amount': data['amount'],
                'description': data['description'] if data['description'] else '',
                'payment_uuid': data['paymentUuid'],
               
            })

            return {
                    'status': True,
                    'is_ivoice': True,
                    'invoice_state': invoice.state,
                    'message': 'Hóa đơn đã được ghi nhận.'
                }
        except Exception as e:
            return {
                'status': False,
                'is_ivoice': False,
                'invoice_state': 'error',
                'message': f"Lỗi hệ thống: {str(e)}"
            }
         