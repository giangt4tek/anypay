import uuid
import hashlib
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ApiKey(models.Model):
    _name = 'api.key'
    _description = 'API Key cấp tạm thời cho client'
    _rec_name = 'name'

    name = fields.Char(
        string="API Key",
        required=True,
        readonly=True,
        default=lambda self: str(uuid.uuid4())
    )

    t4tek_acc = fields.Many2one(
        't4tek.bank.account',
        string="Tài khoản Ngân hàng",
        required=True,
        ondelete="cascade"
    )

    user_id = fields.Many2one(
        'res.users',
        string="Người tạo",
        required=False,
        default=lambda self: self.env.uid
    )

    allowed_ips = fields.Text(
        string="IP Whitelist (mỗi dòng 1 IP)",
        help="Chỉ các IP này mới được phép gọi API bằng key này. Để trống nếu không giới hạn."
    )

    scope = fields.Selection([
        ('read', 'Chỉ đọc'),
        ('write', 'Đọc + ghi'),
        ('full', 'Toàn quyền')
    ], default='read', required=True)

    expired_at = fields.Datetime(string="Hết hạn", required=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_key', 'unique(name)', 'API key phải là duy nhất.')
    ]

    # ----------------------------------------------------
    # Hàm xác thực
    # ----------------------------------------------------
    @api.model
    def is_valid(self, key, ip=None, scope_required=None):
        record = self.search([('name', '=', key), ('active', '=', True)], limit=1)
        if not record:
            _logger.warning("API KEY không hợp lệ: %s", key)
            return False

        now = fields.Datetime.now()
        if record.expired_at and record.expired_at < now:
            _logger.warning("API KEY đã hết hạn: %s", key)
            return False

        if ip:
            allowed = [ip.strip() for ip in (record.allowed_ips or '').splitlines() if ip.strip()]
            if allowed and ip not in allowed:
                _logger.warning("IP %s không nằm trong whitelist của key %s", ip, key)
                return False

        # So sánh cấp độ quyền
        scope_level = {'read': 1, 'write': 2, 'full': 3}
        current = scope_level.get(record.scope, 0)
        required = scope_level.get(scope_required, 0)
        if scope_required and current < required:
            _logger.warning("Scope không đủ: %s (yêu cầu %s)", record.scope, scope_required)
            return False

        return True
