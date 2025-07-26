from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class BankContact(models.Model):
      _name = 'bank.contact'
      _description = 'Bank Information'

      bank_code = fields.Char(string='Mã ngân hàng', required=True)
      _sql_constraints = [('bank_code_unique', 'unique(bank_code)', 'Ngân hàng này đã có.')]
      bank_name = fields.Char(string='Tên ngân hàng', required=True)
      api_url = fields.Char(string="URL gọi API của ngân hàng")
      
      
      @api.model
      def write(self, vals):
        # Xử lý bank_code nếu có đúng quy tắc
        if vals.get('bank_code'):
           vals['bank_code'] = vals['bank_code'].replace(' ', '_').upper()
     
        return super(BankContact, self).write(vals)
      