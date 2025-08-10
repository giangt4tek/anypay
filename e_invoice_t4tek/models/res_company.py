# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_vn_edi_username = fields.Char(
        string='e_invoice Username',
        groups='base.group_system',
    )

    l10n_vn_edi_password = fields.Char(
        string='e_invoice Password',
        groups='base.group_system',
    )

    client_id = fields.Char(
        string='Client ID',
        groups='base.group_system',
    )

    client_secret = fields.Char(
        string='Client Secret',
        groups='base.group_system',
    )

    l10n_vn_edi_token_type = fields.Char(
        string='e_invoice Token Type',
        groups='base.group_system',
        readonly=True,
    )
    
    l10n_vn_edi_token = fields.Char(
        string='e_invoice Access Token',
        groups='base.group_system',
        readonly=True,
    )
    
    l10n_vn_edi_token_expiry = fields.Datetime(
        string='e_invoice Access Token Expiration Date',
        groups='base.group_system',
        readonly=True,
    )

    

    