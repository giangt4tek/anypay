from odoo import fields, models

class AccountMoveSendWizard(models.TransientModel):
    _inherit = 'account.move.send.wizard'

    release_option = fields.Selection([
        ('1', 'Gửi có ký số'),
        ('0', 'Gửi không ký số')
    ],string='send method',
        required=True,
        default='0',)
    
    def action_send_and_print(self):
        self.ensure_one()
        invoice_ids = self.env.context.get('active_ids', [])
        ctx = dict(self.env.context or {})
        ctx['send_release'] = self.release_option
        return super(AccountMoveSendWizard, self.with_context(ctx)).action_send_and_print()