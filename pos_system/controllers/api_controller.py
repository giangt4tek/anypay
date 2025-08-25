import configparser
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
import os
from dateutil.relativedelta import relativedelta

_TIMEOUT = 60 
_API_URL = ''
_TRANSFER_BANK = ''

def get_system_name(var):
    config = configparser.ConfigParser()
    # Lấy thư mục gốc của module (controllers → pos_system)
    module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # Ghép tới file constants.ini
    config_path = os.path.join(module_path, 'data', 'constants.ini')
    # Đọc file .ini
    config.read(config_path)
    return config['system'][var]

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
 
      
    @http.route('/pos/invoice/sync', type='json', auth='none', methods=["POST"], csrf=False)
    def pos_invoice_sync(self, **post):
        
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
                'amount', 'pos'
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

    def check_access_pos(self, SecretKey, PosProvide):
        
        POS = request.env['pos.category'].sudo().search([
            ('secret_key', '=', SecretKey)], limit=1)
   
        error = None
        PosName = get_system_name('name')
        if PosProvide.upper() != PosName.upper(): error = 'Nhà cung cấp POS nhận không phù hợp'
        if not POS:  error = f'Tài khoản này không tồn tại trong POS {PosName}'
        if (POS and PosProvide == PosName) or error is None:
            return {
                "status": True,
                "POSAccount": POS
            }
        else: return {
                "status": False,
                "message": error
                }
            
         
    @http.route('/wallet/invoice/sync', type='json', auth='none', methods=["POST"], csrf=False)
    def wallet_invoice_sync(self, **post):
        
        raw_body = request.httprequest.get_data(as_text=True)
        data = json.loads(raw_body)
       
        # Kiểm tra các trường bắt buộc
        required_fields = [
                'invoiceNumber', 'invoiceDate', 
                'buyerAccount', 'buyerWallet',
                'amount', 'secretKey','POSProvide'
            ]
       
        for name in required_fields:
                if not data.get(name):
                   return {
                         'status': False,
                         'message': f'Trường [{name}] không có dữ liệu'  }
        
        CheckPOS = self.check_access_pos(data['secretKey'], data['POSProvide'])       
        _logger.info(f'----------> POS SYSTEM SYNC CHECK: {CheckPOS}')
        if not CheckPOS['status']: 
            return CheckPOS
        POS = CheckPOS['POSAccount']
        _logger.info(f'----------> POS INFOR: {POS}')
        # Xử lý dữ liệu tạo hóa đơn
        CreateInvoice = {}
        CreateInvoice.update({'invoiceNumber': data.get('invoiceNumber')})
        CreateInvoice.update({'invoiceDate': data.get('invoiceDate')})
        CreateInvoice.update({'buyerAccount': data.get('buyerAccount')})
        CreateInvoice.update({'buyerWallet': data.get('buyerWallet')})
        CreateInvoice.update({'amount': data.get('amount')})
        CreateInvoice.update({'pos': POS.id})
        _logger.info(f'----------> POS SYSTEM SYNC CREATE INVOICE DATA: {CreateInvoice}')
    
        invCreate = self.create_invoice(CreateInvoice)  
        invMess =''
        if invCreate['status']: 
           invMess  = 'Hóa đơn đã được ghi nhận.'
        else:
           invMess= 'Hóa đơn không được ghi nhận.',
        _logger.info(f'----------> MESS: {invCreate}')        
        if POS:
            return {
                'status': True,
                'POS': {
                    'posID': POS.id,
                    'posName': POS.pos_name,
                    'posUser': POS.pos_user,
                    'bankCode': POS.bank_code,
                    'bankAcc': POS.bank_acc,
                },
                'InvoiceIS' :invCreate['status'],
                'message': f'Đồng bộ thành công./{[invMess]}'
                }
        else:
                return {
                    'status': False,
                    'message': 'Không có POS này trong hệ thống.'
                }
       
       
        
               
            
# -------------------------------------- Initialization Handl -------------------------------------------

    def create_invoice(self, data):
        try:
            invocie_is = request.env['invoice.report'].sudo().search([
                ('invoice_number', '=', data['invoiceNumber']),
                ('pos_id', '=', data['pos'].id)], limit=1)
          
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
         