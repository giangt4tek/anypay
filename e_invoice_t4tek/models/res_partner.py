# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    invoice_edi_format = fields.Selection(selection_add=[('vn_e_invoice', 'e_invoice file')])
    l10n_vn_edi_symbol = fields.Many2one(
        comodel_name='e_invoice_t4tek.e_invoice.symbol',
        string='Default Symbol',
        help='If set, this symbol will be used as the default symbol for all invoices of this customer.',
        company_dependent=True,
        copy=False,
    )

    vn_budget_code = fields.Char(
        string='Budget Code',
        help='The budget code of the customer, used for e-invoice.',
        copy=False,
    )

    vn_citizen_identity = fields.Char(
        string='Citizen Identity',
        help='The citizen identity number of the customer, used for e-invoice.',
        copy=False,
    )

    edi_passport = fields.Char(
        string='Passport',
        help='The passport number of the customer, used for e-invoice.',
        copy=False,
    )
