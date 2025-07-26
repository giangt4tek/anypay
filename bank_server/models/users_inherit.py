from odoo import models, api, tools, _
import psycopg2
from odoo.exceptions import UserError

from odoo import models
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin


class Users(models.Model):
    _inherit = 'res.users'

    # def write(self, vals):
    #     id1 = self.env["res.groups"].search([
    #                                         ('full_name', '=',
    #                                          'bank Report System / bank Manager'),
    #                                         ], limit=1)
    #     in_group_manager = 'in_group_' + str(id1[0].id)
    #     id2 = self.env["res.groups"].search(
    #         [('full_name', '=', "Extra Rights / Contact Creation")], limit=1)
    #     in_group_create = 'in_group_' + str(id2[0].id)
    #     if vals.get(in_group_manager, False):
    #         vals[in_group_create] = False
    #     else:
    #         vals[in_group_create] = True

    #     record = super(Users, self).write(vals)
    #     return record
   

    # def create(self, vals):
    #     id1 = self.env["res.groups"].search([
    #                                         ('full_name', '=',
    #                                          'bank Report System / bank Manager'),
    #                                         ], limit=1)
    #     in_group_manager = 'in_group_' + str(id1[0].id)

    #     id2 = self.env["res.groups"].search(
    #         [('full_name', '=', "Extra Rights / Contact Creation")], limit=1)
    #     record = super(Users, self).create(vals)
    #     in_group_create = 'in_group_' + str(id2[0].id)
    #     if vals.get(in_group_manager, False):
    #         vals[in_group_create] = False
    #     else:
            
    #         vals[in_group_create] = True
    #     record.write(vals)

    #     record.partner_id.write({'email': vals['login']})
    #     loyalty_program = self.env['loyalty.program'].search(
    #         [('program_type', '=', "loyalty")], limit=1)
    #     if not loyalty_program:
    #         raise UserError(
    #             _("Connect Coffee cần một chương trình là khách hàng thân thiết!"))

    #     self.env['loyalty.card'].create({
    #         'partner_id': record.partner_id.id,
    #         'program_id': loyalty_program.id,
    #         'expiration_date': False,
    #         'points': 0,
    #     })
    #     return record
