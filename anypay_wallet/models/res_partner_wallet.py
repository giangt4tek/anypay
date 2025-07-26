from odoo import models, fields
import uuid
import logging

_logger = logging.getLogger(__name__)

class ResPartnerWallet(models.Model):
    _inherit = 'res.partner.bank'

    cccd_ids = fields.Many2one('res.partner', string="Căn cước công dân", required=True)

    # scope = fields.Selection([
    #     ('read', 'Chỉ đọc'),
    #     ('write', 'Đọc và ghi'),
    #     ('full', 'Toàn quyền')
    # ], string="Scope quyền API", default='read')

    # api_key = fields.Char(string="API Key", default=lambda self: str(uuid.uuid4()), readonly=True)
    # active_api = fields.Boolean(string="Kích hoạt API", default=True)

    # _sql_constraints = [
    #     ('unique_cccd_api', 'unique(cccd_id)', 'Đối tác này đã có CCCD rồi!')
    # ]

    # def get_bank_customer_data(self):
    #     _logger.info("------------> Fetching bank customer data")
    #     banks = self.search([('active_api', '=', True)], limit=10)
    #     return [{
    #         "id": b.id,
    #         "partner": b.partner_id.name,
    #         "acc_number": b.acc_number,
    #         "cccd_holder": b.cccd_id.name,
    #         "bank": b.bank_id.name if b.bank_id else '',
    #         "api_key": b.api_key,
    #         "scope": b.scope,
    #     } for b in banks]
