from odoo import _, models, fields, api
import json
import requests
from odoo.http import request
from odoo.http import Response
from requests import RequestException
import uuid
import logging
_logger = logging.getLogger(__name__)
from dateutil.relativedelta import relativedelta
_TIMEOUT = 60 
_API_URL = ''
_WALLET = 'VMONNEY'


class TransactionHandle(models.Model):
    _name = 'transaction.handle'
    _description = 'Transaction Handle'

    @api.model
    def _send_request(self, method, url, json_data=None, form_data=None, params=None, headers=None, cookies=None):
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


    def send_transfer_request(self, Data, contact_):
        
        infor_contact = self.env['wallet.contact'].sudo().search([
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
        
        response, error = self._send_request(
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
        
            
    def check_access_wallet(self, accNumber, Wallet):
        walletAccount = self.env['t4tek.wallet.account'].sudo().search([
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
            
                required_fields = ['monneyAmount', 'invoiceNumber', 
                                   'transactionType',
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
             
               self.env['transaction.report'].sudo().create({
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
           
            required_fields = [
                'acc_number', 'invoiceNumber', 'invoiceDate',
                'sellerAccount', 'sellerBank',
                'amount',
            ]
            for name in required_fields:
                if not data.get(name):
                    return {
                         'status': False,
                         'message': f'Trường [{name}] không có dữ liệu'  }
                
            acc = self.check_access_wallet(data['acc_number'], data.get('wallet', _WALLET))
            if not acc['status']: 
                acc['is_ivoice'] = False
                return acc
           
            invocie_is = self.env['invoice.report'].sudo().search([
                ('invoice_number', '=', data['invoiceNumber']),
                 ('acc_number', '=', data['acc_number']), ], limit=1)
            if invocie_is:
                return {
                    'status': False,
                    'is_ivoice': True,
                    'invoice_state': invocie_is.state,
                    'transaction_id': invocie_is.transaction_id,
                    'message': 'Hóa đơn đã tồn tại.'
                }
            
            invoice = self.env['invoice.report'].sudo().create({
                'invoice_number': data.get('invoiceNumber'),
                'invoice_date': data.get('invoiceDate'),
                'pos_local': data.get('POSLocal', ''),
                'seller_name': data.get('sellerName', ''),
                'seller_account': data.get('sellerAccount'),
                'seller_bank_code': data.get('sellerBank'),
                'amount': data.get('amount'),
                'description': data.get('description', ''),
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
        
         