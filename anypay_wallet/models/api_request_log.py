from odoo import models, fields, api
from datetime import datetime
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin

class ApiRequestLog(models.Model):
    _name = 'api.request.log'
    _description = 'Lịch sử gọi API'

    api_key_id = fields.Many2one('api.key')
    path = fields.Char()
    method = fields.Char()
    ip = fields.Char()
    status_code = fields.Integer()
    response = fields.Text()
    created_at = fields.Datetime(default=fields.Datetime.now)
