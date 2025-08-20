from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class WalletContact(models.Model):
      _name = 'wallet.contact'
      _description = 'Wallet Information'

      wallet_code = fields.Char(string='Mã đối tác', required=True)
      _sql_constraints = [('wallet_code_unique', 'unique(wallet_code)', 'Đối tác này đã có.')]
      wallet_name = fields.Char(string='Tên đối tác', required=True)
      api_url = fields.Char(string="URL gọi API của đối tác")
      
      
      @api.model
      def write(self, vals):
        # Xử lý wallet_code nếu có đúng quy tắc
        if vals.get('wallet_code'):
           vals['wallet_code'] = vals['wallet_code'].replace(' ', '_').upper()
     
        return super(WalletContact, self).write(vals)
      