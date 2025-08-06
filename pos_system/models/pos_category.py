from odoo import models, fields, api
from odoo.exceptions import UserError
import uuid
import random
import hashlib
import logging
_logger = logging.getLogger(__name__)


class POSCategory(models.Model):
    _name = 'pos.category'
    _description = 'Quản lý từng POS'
    
    pos_name = fields.Char(string="Tên POS", required=True)
    pos_user = fields.Char(string="Người dùng POS")
    
    bank_code = fields.Char(string="Tên ngân hàng", required=True)
    bank_acc = fields.Char(string="Số tài khoản", required=True)
    
    client_key = fields.Char(string="client Key", readonly=True, copy=False)
    secret_key = fields.Char(string="Secret Key (SHA256)", readonly=True, copy=False)
    
    def generate_key(self):
        for rec in self:
            existing_HashKey = self.search([]).mapped('client_key')
            while True:
                raw_key = str(uuid.uuid4())
                hash_key = hashlib.sha256((raw_key).encode()).hexdigest()
                if hash_key not in existing_HashKey:
                    break
            
            rec.client_key = hash_key
            rec.secret_key = hashlib.md5(raw_key.encode()).hexdigest()


    is_active = fields.Boolean(string='Kích hoạt tài khoản', copy=False,
                               readonly=True, default=False)
    
    def set_is_active_account(self):
        for item in self:
            if item.is_active == True:
                item.is_active = False
            else:
                item.is_active = True
        return {}
      
          
    # @api.model_create_multi
    # def create(self, vals_list):
    #     partner_ids = [vals.get("partner_id") for vals in vals_list if vals.get("partner_id")]

    #     if partner_ids:
    #         # Tìm những partner_id đã có tài khoản
    #         existing = self.search([("partner_id", "in", partner_ids)])
    #         if existing:
    #             raise UserError("Một số người dùng đã có tài khoản ngân hàng.")

    #    # Không được thiếu return:
    #     return super().create(vals_list)

   
  
  
