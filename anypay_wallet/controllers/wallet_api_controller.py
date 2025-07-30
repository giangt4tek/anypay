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


class _Get_WalletApiController(http.Controller):
    _name  = 'wallet.api.controller'

    def send_transfer_request(self, Data, contact_):
        
        infor_contact = request.env['wallet.contact'].sudo().search([
            ('wallet_code', '=', contact_)], limit=1)
        
        if not infor_contact:
            return {
                "status": 'error',
                "message": f'Không tìm thấy đối tác [{contact_}]',
            }
        if not infor_contact.api_url:
            code = infor_contact.get('wallet_code')
            return {
                "status": 'error',
                "message": f'Không có URL API của Ví AnyPay [{code}] ',
            }
        
        response, error = _send_request(
            method='POST',
            url=f'{infor_contact.api_url}api/transaction/transfer/in',
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
       
            result = self._process_transaction(data)
            
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
                  
        result = self._process_transaction(data)
        
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
            
    @http.route('/api/invoice/create', type='json', auth='none', methods=["POST"], csrf=False)
    def create_invoice_debit(self, **post):
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return {'status': 'error', 'message': _('Thiếu hoặc sai định dạng Authorization header')}
    
        token = auth_header.replace("Bearer ", "").strip()
        raw_body = request.httprequest.get_data(as_text=True)
        data = json.loads(raw_body)
        acc_number = data.get('acc_number')
        auth_token = request.env['api.key'].sudo().search([ ('t4tek_acc.acc_number', '=', acc_number),], limit=1)
        
        if (not auth_token and auth_token.name == token) or auth_token.expired_at < fields.Datetime.now():
            return {
                    'status': 'error',
                    'message': 'Token không phù hợp với tài khoản này Hoặc chưa được cấp Hoặc đã hết hạn'}

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
        
    @http.route('/api/invoice/payment', type='json', auth='none', methods=["POST"], csrf=False)
    def invoice_payment(self, **post):
        try:
            raw_body = request.httprequest.get_data(as_text=True)
            data = json.loads(raw_body)

            # === 1. Tách dữ liệu ===
            buyer_info = data.get('buyer', {})
            seller_info = data.get('seller', {})

            invoice_info = {
                'acc_number': buyer_info.get('buyerAccount'),
                'wallet': buyer_info.get('buyerBank'),
                'invoiceNumber': data.get('invoiceNumber'),
                'invoiceDate': data.get('invoiceDate'),
                'POSLocal': data.get('posLocal') or '',
                'amount': data.get('amount'),
                'description': data.get('description') or '',
                'paymentUuid': data.get('paymentUuid'),
                'sellerName': seller_info.get('sellerName'),
                'sellerAccount': seller_info.get('sellerAccount'),
                'sellerBank': seller_info.get('sellerBank'),
            }

           
            # === 2. Ghi nhận hóa đơn ===
            invCreate = self.create_invoice(invoice_info)
            if not invCreate.get('is_ivoice'):
                return {
                    'status': 'error',
                    'message': 'Hóa đơn không được ghi nhận.',
                    'fail': invCreate['message']
                }
            
          
            if invCreate.get('invoice_state') == 'draft':  # Lấy trạng thái hóa đơn nếu cần
            # === 3. Gọi xử lý thanh toán ===
                transfer_data = {
                    'acc_number': buyer_info.get('buyerAccount'),
                    'wallet': buyer_info.get('buyerBank'),
                    'transferAccNumber': seller_info.get('sellerAccount'),
                    'transferWallet': seller_info.get('sellerBank'),
                    'transactionType': 'payment',
                    'monneyAmount': data.get('amount'), }
               
                result = self._process_transaction(transfer_data)
                if result.get('status'):
                    # === 4. Cập nhật trạng thái hóa đơn ===
                    invoice_record = request.env['invoice.report'].sudo().search([
                        ('invoice_number', '=', invoice_info['invoiceNumber']),
                        ('acc_number', '=', invoice_info['acc_number']),
                        ('payment_uuid', '=', invoice_info['paymentUuid'])
                    ], limit=1)
                   
                    invoice_record.set_done(result.get('transactionUuid'))  # Cập nhật trạng thái hóa đơn thành 'done'
            
                    return {
                        "status": 'Success',
                        "transactionUuid": result.get('transactionUuid'),
                        "message": 'Thanh toán thành công'
                    }
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
        

# -------------------------------------- Initialization Handl -------------------------------------------
    def check_access_wallet(self, accNumber, Wallet):
        walletAccount = request.env['t4tek.wallet.account'].sudo().search([
            ('acc_number', '=', accNumber)], limit=1)
        error = None
        if Wallet != _WALLET: error = 'Ví AnyPay nhận không phù hợp'
        if not walletAccount:  error = f'Tài khoản này không tồn tại trong Ví AnyPay {_WALLET}'
        if walletAccount and Wallet == _WALLET:
            return {
                "status": True,
                "walletAccount": walletAccount
            }
        else: return {
                "status": False,
                "message": error
                }

    def _process_transaction(self, data):
        try:
            error = None
            transfer_wallet= ''
            acc = self.check_access_wallet(data['acc_number'], data['wallet'])
            
            if not acc.get('status'): return acc
            
            if data['transactionType'] in ['withdrawal', 'transfer_out', 'payment'] and getattr(acc['walletAccount'], 'balance_account', 0) < data['monneyAmount']:
                return {
                    "status": False,
                    "message": f"Số dư không đủ để thực hiện giao dịch."
                }

        # ---------------   Xử lý khi giao dịch dạng Chuyển khoản --------------------
            if data['transactionType'] == 'transfer_out':
                
                if data['transferAccNumber'] == data['acc_number'] and data['transferWallet'] == _WALLET:
                    return {
                        "status": False,
                        "message": f"Vui lòng không nhập tài khoản của chính mình trong Ví AnyPay hiện tại"
                    }
                
                if data['transferWallet']:
                    transfer_wallet = data['transferWallet']
                else:
                    return {
                        "status": False,
                        "message": f"Không có thông tin Ví AnyPay cần chuyển"
                    }
                
                payload, error = self._add_tranfer_data(data, acc['walletAccount'], transfer_wallet, 'transfer_in')
                if error:
                    return {"status": False, "message": error}
                
                result = self.send_transfer_request(payload, transfer_wallet)
                
                if result.get('status') == 'error':
                    return {"status": False, "message": result.get('message')}
                
                data['transactionUuid'] = payload['transactionUuid']
        # ---------------              *********                  --------------------
                
        # ---------------   Xử lý khi giao dịch dạng Thanh toán hóa đơn --------------------
            if data['transactionType'] == 'payment':
                if data['transferAccNumber'] == data['acc_number'] and data['transferWallet'] == _WALLET:
                    return {
                        "status": False,
                        "message": f"Vui lòng không nhập tài khoản của chính mình trong Ví AnyPay hiện tại"
                    }

                # if data['transferWallet']:
                #     transfer_wallet = data['transferWallet']
                # else:
                #     return {
                #         "status": False,
                #         "message": f"Không có thông tin Ví AnyPay cần chuyển"
                #     }

                
                payload = {}
            
                required_fields = ['monneyAmount',
                                   'acc_number', 'transferAccNumber',
                                   'transferWallet']
        
                for name in required_fields:
                    if not data.get(name):
                        error = f'Trường [{name}] không có dữ liệu'
                        return {"status": False, "message": error}
                    payload[name] = data[name]
        
                # Chỉ thêm UUID nếu không có lỗi
                transactionUuid = str(uuid.uuid4())
                payload['transactionType'] = data['transactionType']
                payload['transactionUuid'] = transactionUuid
                payload['acc_number'] = data['transferAccNumber']
                payload['bank'] = data['transferWallet']
                payload['transferAccNumber'] = data['acc_number']
                payload['transferBank'] = _WALLET
                
                if len(payload) < 6:
                    error = 'Không có đủ thông tin yêu cầu'
                
                if error:
                    return {"status": False, "message": error}
                
                data['transactionUuid'] = payload['transactionUuid']
                
                result = self.send_transfer_request(payload, data['transferWallet'])
                if result.get('status') == 'error':
                    return {"status": False, "message": result.get('message')}
        # ---------------              *********                  --------------------
          
            if data['wallet'] == _WALLET:
             
               request.env['transaction.report'].sudo().create({
                   'account_id': acc['walletAccount'].id,
                   'transaction_type': data['transactionType'],
                   'transaction_date': fields.Datetime.now(),
                   'monney': data['monneyAmount'],
                   'transfer_acc_number': data['transferAccNumber'],
                   'wallet': _WALLET,
                   'transfer_wallet': data['transferWallet'],
                   'transfer_uuid': data['transactionUuid']
               })
          
            return {
                "status": True,
                "transactionUuid": data['transactionUuid'],
                "message": "Information Sync completed successfully!"}
        except Exception as e:
            return {
                "status": False,
                "message": f"Lỗi hệ thống: {str(e)}"
            }
        
    def _add_tranfer_data(self, infor, accNumOut, transfer_wallet, type):
        result = {}
        error =None
        required_fields = ['transactionType', 'monneyAmount',
                           'acc_number', 'transferAccNumber',
                           'wallet', 'transferWallet']

        for name in required_fields:
            if not infor.get(name):
                error = f'Trường [{name}] không có dữ liệu'
                return {}, error
            result[name] = infor[name]

        # Chỉ thêm UUID nếu không có lỗi
       
        transactionUuid = str(uuid.uuid4())
        result['transactionType'] = type
        result['transactionUuid'] = transactionUuid
        result['acc_number'] = result['transferAccNumber']
        result['transferAccNumber'] = accNumOut.acc_number
        result['wallet'] = transfer_wallet
        result['transferWallet'] = _WALLET

        if len(result) < 6:
            error = 'Không có đủ thông tin yêu cầu'
        
        return result, error

    def create_invoice(self, data):
        try:
            
            acc = self.check_access_wallet(data['acc_number'], data['wallet'])
            if not acc['status']: return acc
           
            invocie_is = request.env['invoice.report'].sudo().search([
                ('invoice_number', '=', data['invoiceNumber']),
                 ('acc_number', '=', data['acc_number']),
                 ('payment_uuid', '=', data['paymentUuid'])], limit=1)
            if invocie_is:
                return {
                    'status': False,
                    'is_ivoice': True,
                    'invoice_state': invocie_is.state,
                    'message': 'Hóa đơn đã tồn tại.'
                }
            
            required_fields = [
                'invoiceNumber', 'invoiceDate',
                'sellerName', 'sellerAccount', 'sellerBank',
                'amount', 'paymentUuid'
            ]
            for name in required_fields:
                if not data.get(name):
                    return {
                         'status': False,
                         'message': f'Trường [{name}] không có dữ liệu'  }
            
            invoice = request.env['invoice.report'].sudo().create({
                'invoice_number': data.get('invoiceNumber'),
                'invoice_date': data.get('invoiceDate'),
                'pos_local': data.get('POSLocal') if data.get('POSLocal') else '',
                'seller_name': data.get('sellerName'),
                'seller_account': data.get('sellerAccount'),
                'seller_bank_code': data.get('sellerBank'),
                'amount': data.get('amount'),
                'description': data.get('description') if data.get('description') else '',
                'payment_uuid': data.get('paymentUuid'),
                'account_id': acc['walletAccount'].id,
                'wallet': _WALLET
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
        
         