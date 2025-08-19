# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin

class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    l10n_vn_edi_adjustment_type = fields.Selection(
        selection=[
            ('1', 'Money adjustment'),
            ('2', 'Quantity adjustment'),
            ('3', 'Information adjustment'),
        ],
        string='Adjustment type',
        required=True,
        default='1',
    )
    l10n_vn_edi_agreement_document_name = fields.Char(
        string='Agreement Name',
    )
    l10n_vn_edi_agreement_document_date = fields.Datetime(
        string='Agreement Date',
    )

    def _prepare_default_reversal(self, move):
        # EXTEND 'account'
        values = super()._prepare_default_reversal(move)
        _logger.info('-------------> _prepare_default_reversal')
        # This information is required when sending an adjustment invoice to e_invoice.
        # This is not needed when sending a replacement (as we will be sending the invoice, not the CN) but it doesn't hurt to log it.
        if move._l10n_vn_edi_is_sent():
            values.update({
                'l10n_vn_edi_agreement_document_name': self.l10n_vn_edi_agreement_document_name or 'N/A',
                'l10n_vn_edi_agreement_document_date': self.l10n_vn_edi_agreement_document_date or fields.Datetime.now(),
                'l10n_vn_edi_adjustment_type': self.l10n_vn_edi_adjustment_type,
            })
        return values

    def _modify_default_reverse_values(self, origin_move):
        # EXTEND 'account'
        _logger.info('-------------> _modify_default_reverse_values')
        _logger.info('-----------------> origin_move: %s', origin_move)
        values = super()._modify_default_reverse_values(origin_move)
        _logger.info('-----------------> values: %s', values)
        # This information is REQUIRED on the new invoice that will be sent to e_invoice, if we are creating one.
        if origin_move.l10n_vn_edi_invoice_state not in {False, 'ready_to_send'}:
            values.update({
                'l10n_vn_edi_agreement_document_name': self.l10n_vn_edi_agreement_document_name or 'N/A',
                'l10n_vn_edi_agreement_document_date': self.l10n_vn_edi_agreement_document_date or fields.Datetime.now(),
                'l10n_vn_edi_adjustment_type': self.l10n_vn_edi_adjustment_type,
                'l10n_vn_edi_replacement_origin_id': origin_move.id,
                'status_invoice': '2'
            })
        _logger.info('-----------------> update values: %s', values)
        return values

    def reverse_moves(self, is_modify=False):
        # EXTEND 'account'
        _logger.info('--------------- > Kiểm tra reverse' )
        for move in self.move_ids.filtered(lambda m: m._l10n_vn_edi_is_sent()):
            # If an invoice has a tax code (symbol starts with C) and the code has not been approved by the tax authorities, you cannot adjust/reverse it.

            if move.l10n_vn_edi_invoice_symbol.name:
                invoice_lookup, _error_message = move._l10n_vn_edi_lookup_invoice()
                _logger.info('--------------------> invoice_lookup: %s', invoice_lookup)
                if 'data' in invoice_lookup and invoice_lookup['data'].get('trangthai') != '4':
                    raise UserError(_('Bạn không thể Thay thế/Điều chỉnh HĐ: %s, Nếu HĐ này chưa được cấp mã CQT.\n'
                                      'Vui lòng hủy/hoàn nguyên hóa đơn và tạo hóa đơn mới.', move.name))
            _logger.info('-------------------> %s', is_modify)
            # Makes sure to keep the original status up to date by tagging them by either replaced, or adjusted.
            if is_modify:
                move.l10n_vn_edi_invoice_state = 'replaced'
            else:
                move.l10n_vn_edi_invoice_state = 'adjusted'

        return super().reverse_moves(is_modify)
