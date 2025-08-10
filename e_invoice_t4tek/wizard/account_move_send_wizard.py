from odoo import fields, models

class AccountMoveSendWizard(models.TransientModel):
    _inherit = 'account.move.send.wizard'

    l10n_vn_edi_send_option = fields.Selection([
        ('sign', 'Gửi có ký số'),
        ('no_sign', 'Gửi không ký số')
    ],string='send method',
        required=True,
        default='no_sign',)
