import base64
import io
import re
import time
import uuid
import zipfile
from datetime import datetime, timedelta

import requests
from requests import RequestException

from odoo import _, api, fields, models
from odoo.exceptions import UserError
import logging  # Nhập thư viện logging để ghi lại thông tin và lỗi
_logger = logging.getLogger(__name__)  # Tạo logger để ghi lại thông tin

e_invoice_API_URL = 'https://cphoadonuat.hoadon30s.vn/'
e_invoice_TIMEOUT = 60  # They recommend between 60 and 90 seconds, but 60s is already quite long.


def _l10n_vn_edi_send_request(method, url, json_data=None, form_data=None, params=None, headers=None, cookies=None):
    """ Send a request to the API based on the given parameters. In case of errors, the error message is returned. """
    try:
        if json_data:
            response = requests.request(
                method,
                url,
                json=json_data,
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=e_invoice_TIMEOUT
            )
        elif form_data:
            response = requests.request(
                method,
                url,
                data=form_data,  # Đây là điểm quan trọng cho x-www-form-urlencoded
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=e_invoice_TIMEOUT
            )
        else:
            response = requests.request(
                method,
                url,
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=e_invoice_TIMEOUT
            )
        resp_json = response.json()
        error = None
        if resp_json.get('code') or resp_json.get('error'):
            data = resp_json.get('data') or resp_json.get('error')
            error = _('Error when contacting e_invoice: %s.', data)
        return resp_json, error
    except (RequestException, ValueError) as err:
        return {}, _('Something went wrong, please try again later: %s', err)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # EDI values
    l10n_vn_edi_invoice_state = fields.Selection(
        string='E-Invoice Status',
        selection=[
            ('ready_to_send', 'Ready to send'),
            ('sent', 'Sent'),
            # Set when we write on the payment status
            ('payment_state_to_update', 'Payment status to update'),
            ('canceled', 'Canceled'),
            ('adjusted', 'Adjusted'),
            ('replaced', 'Replaced'),
        ],
        copy=False,
        compute='_compute_l10n_vn_edi_invoice_state',
        store=True,
        readonly=False,
    )
    # This id is important when sending by batches in order to recognize individual invoices.
    l10n_vn_edi_invoice_transaction_id = fields.Char(
        string='e_invoice Transaction ID',
        help='Technical field to store the transaction ID if needed',
        export_string_translation=False,
        copy=False,
    )
    invoice_id_attr = fields.Char(
        string='e_invoice Attachments ID',
        export_string_translation=False,
        copy=False,
    )
    invoice_lookup_code = fields.Char(
        string='e_invoice Lookup code',
        export_string_translation=False,
        copy=False,
    )
    l10n_vn_edi_invoice_symbol = fields.Many2one(
        string='Invoice Symbol',
        comodel_name='e_invoice_t4tek.e_invoice.symbol',
        compute='_compute_l10n_vn_edi_invoice_symbol',
        readonly=False,
        store=True,
    )
    l10n_vn_edi_invoice_number = fields.Char(
        string='e_invoice Number',
        help='Invoice Number as appearing on e_invoice.',
        copy=False,
        readonly=True,
    )
    l10n_vn_edi_reservation_code = fields.Char(
        string='Secret Code',
        help='Secret code that can be used by a customer to lookup an invoice on e_invoice.',
        copy=False,
        readonly=True,
    )
    l10n_vn_edi_issue_date = fields.Datetime(
        string='Issue Date',
        help='Date of issue of the invoice on the e-invoicing system.',
        copy=False,
        readonly=True,
    )
    l10n_vn_edi_e_invoice_file_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute=lambda self: self._compute_linked_attachment_id('l10n_vn_edi_e_invoice_file_id', 'l10n_vn_edi_e_invoice_file'),
        depends=['l10n_vn_edi_e_invoice_file'],
        export_string_translation=False,
    )
    l10n_vn_edi_e_invoice_file = fields.Binary(
        string='e_invoice json File',
        copy=False,
        export_string_translation=False,
    )
    l10n_vn_edi_e_invoice_xml_file_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute=lambda self: self._compute_linked_attachment_id('l10n_vn_edi_e_invoice_xml_file_id', 'l10n_vn_edi_e_invoice_xml_file'),
        depends=['l10n_vn_edi_e_invoice_xml_file'],
        export_string_translation=False,
    )
    l10n_vn_edi_e_invoice_xml_file = fields.Binary(
        string='e_invoice xml File',
        copy=False,
        export_string_translation=False,
    )
    l10n_vn_edi_e_invoice_pdf_file_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute=lambda self: self._compute_linked_attachment_id('l10n_vn_edi_e_invoice_pdf_file_id', 'l10n_vn_edi_e_invoice_pdf_file'),
        depends=['l10n_vn_edi_e_invoice_pdf_file'],
        export_string_translation=False,
    )
    l10n_vn_edi_e_invoice_pdf_file = fields.Binary(
        string='e_invoice pdf File',
        copy=False,
        export_string_translation=False,
    )
    # Replacement/Adjustment fields
    l10n_vn_edi_agreement_document_name = fields.Char(
        string='Agreement Name',
        copy=False,
    )
    l10n_vn_edi_agreement_document_date = fields.Datetime(
        string='Agreement Date',
        copy=False,
    )
    l10n_vn_edi_adjustment_type = fields.Selection(
        string='Adjustment type',
        selection=[
            ('1', 'Money adjustment'),
            ('2', 'Information adjustment'),
        ],
        copy=False,
    )
    # Only used in case of replacement invoice.
    l10n_vn_edi_replacement_origin_id = fields.Many2one(
        comodel_name='account.move',
        string='Replacement of',
        copy=False,
        readonly=True,
        check_company=True,
        export_string_translation=False,
    )
    l10n_vn_edi_reversed_entry_invoice_number = fields.Char(
        string='Revered Entry e_invoice Number',  # Need string here to avoid same label warning
        related='reversed_entry_id.l10n_vn_edi_invoice_number',
        export_string_translation=False,
    )

    @api.depends('l10n_vn_edi_invoice_state')
    def _compute_show_reset_to_draft_button(self):
        # EXTEND 'account'
        super()._compute_show_reset_to_draft_button()
        self.filtered(lambda m: m._l10n_vn_need_cancel_request()).show_reset_to_draft_button = False

    @api.depends('l10n_vn_edi_invoice_state')
    def _compute_need_cancel_request(self):
        # EXTEND 'account' to add dependencies
        return super()._compute_need_cancel_request()

    @api.depends('payment_state')
    def _compute_l10n_vn_edi_invoice_state(self):
        """ Automatically set the state to payment_state_to_update when the payment state is updated.

        This is a bit simplistic, as it can be wrongly set (for example, no need to send when going from in_payment to paid)
        But this shouldn't be an issue since the logic to send the update will check if anything need to change.
        """
        for invoice in self:
            if invoice.country_code == 'VN' and invoice.l10n_vn_edi_invoice_state == 'send':
                invoice.l10n_vn_edi_invoice_state = 'payment_state_to_update'
            else:
                invoice.l10n_vn_edi_invoice_state = invoice.l10n_vn_edi_invoice_state

    @api.depends('company_id', 'partner_id')
    def _compute_l10n_vn_edi_invoice_symbol(self):
        """ Use the property l10n_vn_edi_symbol to set a default invoice symbol. """
        for invoice in self:
            if invoice.country_code == 'VN':
                # Even if there was a value already set, we assume that it should be updated if the partner is changed.
                invoice.l10n_vn_edi_invoice_symbol = invoice.partner_id.l10n_vn_edi_symbol
            else:
                invoice.l10n_vn_edi_invoice_symbol = False

    def button_request_cancel(self):
        # EXTEND 'account'
        if self._l10n_vn_need_cancel_request():
            return {
                'name': _('Invoice Cancellation'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'e_invoice_t4tek.cancellation',
                'target': 'new',
                'context': {'default_invoice_id': self.id},
            }

        return super().button_request_cancel()

    def _get_fields_to_detach(self):
        # EXTENDS account
        fields_list = super()._get_fields_to_detach()
        fields_list.extend(['l10n_vn_edi_e_invoice_file', 'l10n_vn_edi_e_invoice_xml_file','l10n_vn_edi_e_invoice_pdf_file'])
        return fields_list

    def _l10n_vn_edi_fetch_invoice_file_data(self, file_format):
        """ Helper to try fetching a few time in case the files are not yet ready. """
        self.ensure_one()
       
        files_data, error_message = self._l10n_vn_edi_try_fetch_invoice_file_data()
        
        if error_message:
            return '', error_message
        
        # Sometimes the documents are not available right away. This is quite rare, but I saw it happen a few times.
        # To handle that we will try up to three time to fetch the document => The impact should be negligible.
        threshold = 1
        while not files_data['hash'] and threshold < 3:
            time.sleep(0.125 * threshold)
            files_data, error_message = self._l10n_vn_edi_try_fetch_invoice_file_data()
            threshold += 1
        
        original_url = files_data['hash']
        old_url = re.search(r'^https.*?\.vn/', original_url).group()
        new_url = original_url.replace(old_url, e_invoice_API_URL)
        if file_format == 'PDF':
            new_url +=  "/pdf-download"
        elif file_format == 'XML' or file_format == 'ZIP':
            new_url +=  "/xml-download"
        # Tải file
        try:
            file_invoice = requests.get(new_url, timeout=20)
        except requests.exceptions.Timeout:
           return None, _("Quá thời gian chờ khi tải file")
        except requests.exceptions.RequestException as e:
           return None, _("Lỗi khi tải file: %s" % str(e))
        
        # Kiểm tra nếu tải không thành công
        if file_invoice.status_code != 200:
            error_message= file_invoice.status_code
        else: # Kiểm tra định dạng file
            allowed_mime_types = {
                       'PDF': 'application/pdf',
                       'ZIP': 'application/zip',
                       'XML': 'application/xml',
                       'JSON': 'application/json',}

            expected_mimetype = allowed_mime_types.get(file_format.upper())  # Ví dụ file_format = 'ZIP'
            content_type = file_invoice.headers.get('Content-Type', '')
            
            if expected_mimetype and expected_mimetype != content_type:
                error_message = f"Not file type format: expected {expected_mimetype}, got {content_type}"
        
        return file_invoice, error_message

    def _l10n_vn_edi_try_fetch_invoice_file_data(self):
        """
        Query e_invoice in order to fetch the data representation of the invoice, either zip or pdf.
        """
        self.ensure_one()
        if not self._l10n_vn_edi_is_sent():
            return {}, _("In order to download the invoice's PDF file, you must first send it to e_invoice")

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        token_type, access_token, error = self._l10n_vn_edi_get_access_token(scope_type='invoice-lookup')
        if error:
            return {}, error
        
        return _l10n_vn_edi_send_request(
            method='POST',
            url=f'{e_invoice_API_URL}api/invoice/lookup',
            json_data={
                'matracuu': self.invoice_lookup_code,
                'conversion': 0  
            },
            headers={'authorization':f"{token_type} {access_token}",
                     'Content-Type': 'application/json'},
        )

    def _l10n_vn_edi_fetch_invoice_xml_file_data(self):
        """
        Query e_invoice in order to fetch the xsl and xml data representation of the invoice.

        Returns a list of tuple with both file names, mimetype, content and the field it should be stored in.
        """
        self.ensure_one()
        
        files_data, error_message = self._l10n_vn_edi_fetch_invoice_file_data('ZIP')
       
        if error_message:
            return files_data, error_message
       
        file_bytes = files_data.content
       
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zip_file:
            for zip_info in zip_file.infolist():
                if zip_info.filename.endswith('.xml'):
                    return {
                        'name': zip_info.filename,
                        'mimetype': 'application/xml',
                        'raw': zip_file.read(zip_info),
                        'res_field': 'l10n_vn_edi_e_invoice_xml_file',
                    }, ""

    def _l10n_vn_edi_fetch_invoice_pdf_file_data(self):
        """
        Query e_invoice in order to fetch the pdf data representation of the invoice.

        Returns a tuple with the pdf name, mimetype, content and field.
        """
        self.ensure_one()
        files_data, error_message = self._l10n_vn_edi_fetch_invoice_file_data('PDF')
        
        if error_message:
            return files_data, error_message
        file_name = "invoice.pdf"

        disposition = files_data.headers.get("Content-Disposition", "")
        match = re.search(r'filename="?([^"]+)"?', disposition)
        if match:
            file_name = match.group(1)
        file_bytes = files_data.content
    
        return {
            'name': file_name,
            'mimetype': 'application/pdf',
            'raw': file_bytes,
            'res_field': 'l10n_vn_edi_e_invoice_pdf_file',
        }, ""

    def action_l10n_vn_edi_update_payment_status(self):
        """ Send a request to update the payment status of the invoice. """
        invoices = self.filtered(lambda i: i.l10n_vn_edi_invoice_state == 'payment_state_to_update')

        if not invoices:
            return

        # == Lock ==
        self.env['res.company']._with_locked_records(invoices)

        for invoice in invoices:
            e_invoice_status = 'unpaid'

            # e_invoice will return a NOT_FOUND_DATA error if the status in Odoo matches the one on their side.
            # Because of that we wouldn't be able to differentiate a real issue (invoice on our side not matching theirs)
            # With simply a status already up to date. So we need to check the status first to see if we need to update.
            invoice_lookup, error_message = invoice._l10n_vn_edi_lookup_invoice()
            if error_message:
                raise UserError(error_message)

            if 'result' in invoice_lookup:
                invoice_data = invoice_lookup['result'][0]
                if invoice_data['status'] == 'Chưa thanh toán':  # Vietnamese for 'unpaid'
                    e_invoice_status = 'unpaid'
                else:
                    e_invoice_status = 'paid'

            params = {
                'supplierTaxCode': invoice.company_id.vat,
                'invoiceNo': invoice.l10n_vn_edi_invoice_number,
                'strIssueDate': invoice._l10n_vn_edi_format_date(invoice.l10n_vn_edi_issue_date),
            }

            if invoice.payment_state in {'in_payment', 'paid'} and e_invoice_status == 'unpaid':
                # Mark the invoice as paid
                endpoint = f'{e_invoice_API_URL}InvoiceAPI/InvoiceWS/updatePaymentStatus'
                params['templateCode'] = invoice.l10n_vn_edi_invoice_symbol.invoice_template_id.name
            elif invoice.payment_state not in {'in_payment', 'paid'} and e_invoice_status == 'paid':
                # Mark the invoice as not paid
                endpoint = f'{e_invoice_API_URL}InvoiceAPI/InvoiceWS/cancelPaymentStatus'
            else:
                continue

            token_type, access_token, error = self._l10n_vn_edi_get_access_token(scope_type='create-invoice')
            if error:
                raise UserError(error)

            _request_response, error_message = _l10n_vn_edi_send_request(
                method='POST',
                url=endpoint,
                params=params,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded;',
                },
                cookies={'access_token': access_token},
            )

            if error_message:
                raise UserError(error_message)

            # Revert back to the sent state as the status is up-to-date.
            invoice.l10n_vn_edi_invoice_state = 'send'

            if self._can_commit():
                self._cr.commit()

    def _l10n_vn_need_cancel_request(self):
        return self._l10n_vn_edi_is_sent() and self.l10n_vn_edi_invoice_state != 'canceled'

    def _need_cancel_request(self):
        # EXTEND 'account'
        return super()._need_cancel_request() or self._l10n_vn_need_cancel_request()

    def _post(self, soft=True):
        # EXTEND 'account'
        posted = super()._post(soft=soft)

        # Ensure to tag the move as 'Ready to send' upon posting if it makes sense.
        posted.filtered(
            lambda invoice:
                invoice.country_code == 'VN'
                and invoice.is_sale_document()
                and not invoice._l10n_vn_edi_is_sent()
        ).l10n_vn_edi_invoice_state = 'ready_to_send'

        return posted

    # -------------------------------------------------------------------------
    # API METHODS
    # -------------------------------------------------------------------------

    def _l10n_vn_edi_check_invoice_configuration(self):
        """ Some checks that are used to avoid common errors before sending the invoice. """
        self.ensure_one()
        company = self.company_id
        commercial_partner = self.commercial_partner_id
        errors = []
        #không set username and password -> client_id và client_secret ---- GX
        # if not company.l10n_vn_edi_username or not company.l10n_vn_edi_password:
        #     errors.append(_('e_invoice credentials are missing on company %s.', company.display_name))
        if not company.client_id or not company.client_secret:
              errors.append(_('e_invoice credentials are missing on company %s.', company.display_name))
        # Tạm thời không kiểm tra VAT vì có thể không có -- GX
        # if not company.vat:
        #     errors.append(_('VAT number is missing on company %s.', company.display_name))
        company_phone = company.phone and self._l10n_vn_edi_format_phone_number(company.phone)
        if company_phone and not company_phone.isdecimal():
            errors.append(_('Phone number for company %s must only contain digits or +.', company.display_name))
        commercial_partner_phone = commercial_partner.phone and self._l10n_vn_edi_format_phone_number(commercial_partner.phone)
        if commercial_partner_phone and not commercial_partner_phone.isdecimal():
            errors.append(_('Phone number for partner %s must only contain digits or +.', commercial_partner.display_name))
        if not self.l10n_vn_edi_invoice_symbol:
            errors.append(_('The invoice symbol must be provided.'))
        if self.l10n_vn_edi_invoice_symbol and not self.l10n_vn_edi_invoice_symbol.invoice_template_id:
            errors.append(_("The invoice symbol's template must be provided."))
        if self.move_type == 'out_refund' and (not self.reversed_entry_id or not self.reversed_entry_id._l10n_vn_edi_is_sent()):
            errors.append(_('You can only send a credit note linked to a previously sent invoice.'))
        # tạm thời không kiểm tra partner_id vì có thể không có -- GX
        # if not self.partner_id.street or not self.partner_id.city or not self.partner_id.state_id or not self.partner_id.country_id:
        #     errors.append(_('The street, city, state and country of partner %s must be provided.', self.partner_id.display_name))
        # if not company.street or not company.state_id or not company.country_id:
        #     errors.append(_('The street, state and country of company %s must be provided.', company.display_name))
        if self.company_currency_id.name != 'VND':
            vnd = self.env.ref('base.VND')
            rate = vnd.with_context(date=self.invoice_date or self.date).rate
            if not vnd.active or rate == 1:
                errors.append(_('Please make sure that the VND currency is enabled, and that the exchange rates are set.'))
        return errors

    def _l10n_vn_edi_send_invoice(self, invoice_json_data):
        """ Send an invoice to the e_invoice system.

        Handles lookup on the system in order to ensure that the invoice was not sent successfully yet in case of
        timeout or other unforeseen error.
        """

        self.ensure_one()

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        invoice_data = {}

        if not invoice_data:
            # Send the invoice to the system
           
            token_type, access_token, error = self._l10n_vn_edi_get_access_token(scope_type='create-invoice')
        
            if error:
                return [error]
          
            request_response, error_message = _l10n_vn_edi_send_request(
                method='POST',
                url=f'{e_invoice_API_URL}api/invoice/create',
                json_data=invoice_json_data,
                headers={'authorization':f"{token_type} {access_token}",
                         'Content-Type': 'application/json'},
            )
            
            if error_message:
                return [error_message]
            status = request_response['status']
            message = request_response['message']

        if status == 200:
            self.write({
                'invoice_id_attr': request_response['id_attr'],
                'invoice_lookup_code': request_response['lookup_code'],
                'l10n_vn_edi_invoice_state': 'send',
            })
            
        else:
            # If the status is not 200, we assume that the invoice was not sent successfully.
            # We can still store the error message in the chatter.
            _logger.error('Error when sending invoice %s to e_invoice: %s', self.name, message)
            return

        if self._can_commit():
            self._cr.commit()
       

    def _l10n_vn_edi_cancel_invoice(self, reason, agreement_document_name, agreement_document_date):
        """ Send a request to cancel the invoice. """
        self.ensure_one()

        # == Lock ==
        self.env['res.company']._with_locked_records(self)

        # If no error raised, we try to cancel it on the EDI.
        token_type, access_token, error = self._l10n_vn_edi_get_access_token(scope_type='cancel-invoice')
        if error:
            raise UserError(error)
        _logger.info('-------------> xóa inovice có id_attr: %s', self.invoice_id_attr)
        _request_response, error_message = _l10n_vn_edi_send_request(
            method='POST',
            url=f'{e_invoice_API_URL}api/invoice/cancel',
            json_data={
                'id_attr': self.invoice_id_attr,
                'reason': reason,
                'date_cancel': self.l10n_vn_edi_issue_date.strftime('%Y-%m-%d'),
                'send': 0,
                'cus_name':'',
                'cus_email': '',
                'type': 'HDGTGT',
            },
            headers={'authorization':f"{token_type} {access_token}",
                     'Content-Type': 'application/json'},
        )
        _logger.info('-------------> response cancel: %s', _request_response)
        if error_message:
            raise UserError(error_message)

        self.l10n_vn_edi_invoice_state = 'canceled'

        try:
            self._check_fiscal_lock_dates()
            self.line_ids._check_tax_lock_date()

            self.button_cancel()

            self.with_context(no_new_invoice=True).message_post(
                body=_('The invoice has been canceled for reason: %(reason)s', reason=reason),
            )
        except UserError as e:
            self.with_context(no_new_invoice=True).message_post(
                body=_('The invoice has been canceled on e_invoice for reason: %(reason)s'
                       'But the cancellation in Odoo failed with error: %(error)s', reason=reason, error=e),
            )

        if self._can_commit():
            self._cr.commit()

    def button_draft(self):
        # EXTEND account
        # When going from canceled => draft, we ensure to clear the edi fields so that the invoice can be resent if required.
        cancelled_e_invoices = self.filtered(
            lambda i: i.country_code == 'VN' and i.l10n_vn_edi_invoice_state == 'canceled' and i.state == 'cancel'
        )
        res = super().button_draft()
        cancelled_e_invoices.write({
            'l10n_vn_edi_invoice_transaction_id': False,
            'l10n_vn_edi_invoice_number': False,
            'l10n_vn_edi_reservation_code': False,
            'l10n_vn_edi_issue_date': False,
            'l10n_vn_edi_invoice_state': False,
        })
        # Cleanup the files as well. They will still be available in the chatter.
        cancelled_e_invoices.l10n_vn_edi_e_invoice_xml_file_id.unlink()
        cancelled_e_invoices.l10n_vn_edi_e_invoice_pdf_file_id.unlink()
        cancelled_e_invoices.l10n_vn_edi_e_invoice_file_id.unlink()
        return res

    def _l10n_vn_edi_generate_invoice_json(self):
        """ Return the dict of data that will be sent to the api in order to create the invoice. """
        # We leave the summarized information computation to e_invoice.
        self.ensure_one()
        # This MUST match chronologically with the sequence they generate on their system, which is why it is set to now.
        self.l10n_vn_edi_issue_date = fields.Datetime.now()
        # json_values = {}
        # self._l10n_vn_edi_add_general_invoice_information(json_values)
        #self._l10n_vn_edi_add_buyer_information(json_values)
        #self._l10n_vn_edi_add_seller_information(json_values)
        #self._l10n_vn_edi_add_payment_information(json_values)
        #self._l10n_vn_edi_add_item_information(json_values)
        #self._l10n_vn_edi_add_tax_breakdowns(json_values)
        json_values = self._add_general_invoice_information()
        return json_values
    
    # region Create Invoice Information
    def _add_general_invoice_information(self):
        """ General invoice information, such as the model number, invoice symbol, type, date of issues, ... """
        self.ensure_one()

        invoice_type = self.l10n_vn_edi_invoice_symbol.invoice_template_id.template_invoice_type
        invoice_name = dict(self.env['e_invoice_t4tek.e_invoice.template']._fields['template_invoice_type'].selection).get(invoice_type)
        action = ['create', 'update', 'replace', 'adjust']
      
        invoice_data = {
            'init_invoice': invoice_type,
            'action': action[0],
            'id_attr': '',
            'reference_id': '',
            'id_partner': '',
            'invoice_type': '',
            'name': invoice_name,
            "serial" : self.l10n_vn_edi_invoice_symbol.name,
            'date_export' : self.l10n_vn_edi_issue_date.strftime('%Y-%m-%d'),
            'order_code' : self.name,
            'currency' : self.currency_id.name,
            'discount' : 0,
            'vat_rate' : self.company_id.vat,
            'vat_rate_other' : "",
            'vat_amount' : self.amount_tax_signed,
            'total' : self.amount_untaxed_in_currency_signed,
            'amount' : self.amount_total_in_currency_signed,
            'amount_in_words' : "Sáu mươi sáu nghìn đồng",
            'round' : True,
            'payment_type' : 1,
            **self._add_buyer_information(),
            'detail' : self._add_item_information(),
            'autoSign': 0,
            'returnXml' : 0,
            
        }
        return invoice_data
    
    def _add_buyer_information(self):
        """ Create and return the buyer information for the current invoice. """
        self.ensure_one()
        
        buyer_name = self.partner_id.name or "Khách lẻ"
        commercial_partner_phone = self.commercial_partner_id.phone and self._l10n_vn_edi_format_phone_number(self.commercial_partner_id.phone)
        
        buyer_information = {
            'customer_code' : self.partner_id.id or "KH_LE",
            'cus_buyer':  "" if self.partner_id.is_company else buyer_name, 
            'cus_name': buyer_name if self.partner_id.is_company else "",
            'cus_taxCode' : self._get_valid_vat(),
            'cus_address' : self._get_address_inline(),
            'cus_phone' : commercial_partner_phone or '',
            'cus_email' : self.commercial_partner_id.email or '',
            'cus_email_cc' : "",
        }

        if self.partner_bank_id:
            buyer_information.update({
                'cus_bank_name': self.partner_bank_id.bank_name,
                'cus_bank_no': self.partner_bank_id.acc_number,
            })

        return  buyer_information

    def _add_item_information(self):
        self.ensure_one()
        product_lines = self.invoice_line_ids.filtered(lambda ln: ln.display_type == 'product')
        items_information = []
        code_map = {
            'product': 1,
            'line_note': 2,
            'discount': 3,
            'note': 4 }

        for idx, line in enumerate(product_lines, start=1):
            # For credit notes amount, we send negative values (reduces the amount of the original invoice)
            sign = 1 if self.move_type == 'out_invoice' else -1
            
            item_information = {
                'num': idx,  # Sequence is used to order the items.
                'name': line.name,
                'code': line.product_id.code or '',
                'unit': line.product_uom_id.name,
                'quantity': line.quantity,
                'price': line.price_unit * sign,
                'total': line.price_total * sign,
                'discount': line.discount or 0.0,
                'discountAmount': (line.price_total - line.price_subtotal) * sign,
                'feature': code_map.get(line.display_type, 1),  # Default to product if not found
            }
            items_information.append(item_information)
    
        return items_information
    
    def _get_valid_vat(self):
        raw_vat = (self.commercial_partner_id.vat or "").strip()
        # Kiểm tra MST chính: đúng 10 số
        if re.fullmatch(r'\d{10}', raw_vat):
            return raw_vat
        # Kiểm tra MST đơn vị phụ thuộc: 10 số - 3 số
        if re.fullmatch(r'\d{10}-\d{3}', raw_vat):
            return raw_vat
        # Trả về chuỗi rỗng nếu không hợp lệ
        return ""
    
    def _get_address_inline(self):
        raw_address = self.partner_id.contact_address_inline or ""
        address = raw_address.split(',', 1)[1].strip() if ',' in raw_address else raw_address

        return address


  # endregion 
    
    def _l10n_vn_edi_add_general_invoice_information(self, json_values):
        """ General invoice information, such as the model number, invoice symbol, type, date of issues, ... """
        self.ensure_one()
        # Khai báo này dành cho HDDT Viettel --- GX
        invoice_data = {
            'transactionUuid': str(uuid.uuid4()),
            'invoiceType': self.l10n_vn_edi_invoice_symbol.invoice_template_id.template_invoice_type,
            'templateCode': self.l10n_vn_edi_invoice_symbol.invoice_template_id.name,
            'invoiceSeries': self.l10n_vn_edi_invoice_symbol.name,
            # This timestamp is important as it is used to check the chronological order of Invoice Numbers.
            # Since this xml is generated upon posting, just like the invoice number, using now() should keep that order
            # correct in most case.
            'invoiceIssuedDate': self._l10n_vn_edi_format_date(self.l10n_vn_edi_issue_date),
            'currencyCode': self.currency_id.name,
            'adjustmentType': '1',  # 1 for original invoice, which is the case during first issuance.
            'paymentStatus': self.payment_state in {'in_payment', 'paid'},
            'cusGetInvoiceRight': True,  # Set to true, allowing the customer to see the invoice.
            'validation': 1,  # Set to 1, e_invoice will validate tax information while processing the invoice.
        }

        # When invoicing in a foreign currency, we need to provide the rate, or it will default to 1.
        if self.currency_id.name != 'VND':
            invoice_data['exchangeRate'] = self.env['res.currency']._get_conversion_rate(
                from_currency=self.currency_id,
                to_currency=self.env.ref('base.VND'),
                company=self.company_id,
                date=self.invoice_date or self.date,
            )

        adjustment_origin_invoice = None
        if self.move_type == 'out_refund':  # Credit note are used to adjust an existing invoice
            adjustment_origin_invoice = self.reversed_entry_id
        elif self.l10n_vn_edi_replacement_origin_id:  # 'Reverse and create invoice' is used to issue a replacement invoice
            adjustment_origin_invoice = self.l10n_vn_edi_replacement_origin_id

        if adjustment_origin_invoice:
            invoice_data.update({
                'adjustmentType': '5' if self.move_type == 'out_refund' else '3',  # Adjustment or replacement
                'adjustmentInvoiceType': self.l10n_vn_edi_adjustment_type or '',
                'originalInvoiceId': adjustment_origin_invoice.l10n_vn_edi_invoice_number,
                'originalInvoiceIssueDate': self._l10n_vn_edi_format_date(adjustment_origin_invoice.l10n_vn_edi_issue_date),
                'originalTemplateCode': adjustment_origin_invoice.l10n_vn_edi_invoice_symbol.invoice_template_id.name,
                'additionalReferenceDesc': self.l10n_vn_edi_agreement_document_name,
                'additionalReferenceDate': self._l10n_vn_edi_format_date(self.l10n_vn_edi_agreement_document_date),
            })

        json_values['generalInvoiceInfo'] = invoice_data

    def _l10n_vn_edi_add_seller_information(self, json_values):
        """ Create and return the seller information for the current invoice. """
        self.ensure_one()
        company_phone = self.company_id.phone and self._l10n_vn_edi_format_phone_number(self.company_id.phone)
        seller_information = {
            'sellerLegalName': self.company_id.name,
            'sellerTaxCode': self.company_id.vat,
            'sellerAddressLine': self.company_id.street,
            'sellerPhoneNumber': company_phone or '',
            'sellerEmail': self.company_id.email,
            'sellerDistrictName': self.company_id.state_id.name,
            'sellerCountryCode': self.company_id.country_id.code,
            'sellerWebsite': self.company_id.website,
        }

        if self.partner_bank_id:
            seller_information.update({
                'sellerBankName': self.partner_bank_id.bank_name,
                'sellerBankAccount': self.partner_bank_id.acc_number,
            })

            if self.partner_bank_id.proxy_type == 'merchant_id':
                seller_information.update({
                    'merchantCode': self.partner_bank_id.proxy_value,
                    'merchantName': self.company_id.name,
                    'merchantCity': self.company_id.city,
                })

        json_values['sellerInfo'] = seller_information

    def _l10n_vn_edi_add_payment_information(self, json_values):
        """ Create and return the payment information for the current invoice. Not fully supported. """
        self.ensure_one()
        json_values['payments'] = [{
            # We need to provide a value but when we send the invoice, we may not have this information.
            # According to VN laws, if the payment method has not been determined, we can fill in TM/CK.
            # TM is for bank transfer, CK is for cash payment.
            'paymentMethodName': 'TM/CK',
        }]

    def _l10n_vn_edi_add_tax_breakdowns(self, json_values):
        """ Create and return the tax breakdown of the current invoice. """
        self.ensure_one()

        def grouping_key_generator(base_line, tax_data):
            # Requirement is to generate a tax breakdown per taxPercentage
            return {'tax_percentage': tax_data['tax'].amount or -2}

        tax_breakdowns = []

        tax_details_grouped = self._prepare_invoice_aggregated_taxes(grouping_key_generator=grouping_key_generator)
        for tax_percentage, tax_percentage_values in tax_details_grouped['tax_details'].items():
            tax_breakdowns.append({
                'taxPercentage': tax_percentage['tax_percentage'],
                'taxableAmount': tax_percentage_values['base_amount_currency'],
                'taxAmount': tax_percentage_values['tax_amount_currency'],
                'taxableAmountPos': self.move_type == 'out_invoice',  # For adjustment invoice, the amount should be considered as negative.
                'taxAmountPos': self.move_type == 'out_invoice',  # Same
            })

        json_values['taxBreakdowns'] = tax_breakdowns

    def _l10n_vn_edi_lookup_invoice(self):
        """ Lookup on invoice, returning its current details on e_invoice. """
        self.ensure_one()
        type_token, access_token, error = self._l10n_vn_edi_get_access_token(scope_type='invoice-lookup')
        if error:
            return {}, error

        invoice_data, error_message = _l10n_vn_edi_send_request(
            method='POST',
            url=f'{e_invoice_API_URL}InvoiceAPI/InvoiceWS/searchInvoiceByTransactionUuid',
            params={
                'supplierTaxCode': self.company_id.vat,
                'transactionUuid': self.l10n_vn_edi_invoice_transaction_id,
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded;',
            },
            cookies={'access_token': access_token},
        )
        return invoice_data, error_message

    def _l10n_vn_edi_get_access_token(self, scope_type):
        """ Return an access token to be used to contact the API. Either take a valid stored one or get a new one. """

        self.ensure_one()
        credentials_company = self._l10n_vn_edi_get_credentials_company()
        # First, check if we have a token stored and if it is still valid.
        if scope_type == 'create-invoice' and credentials_company.l10n_vn_edi_token_type and credentials_company.l10n_vn_edi_token and credentials_company.l10n_vn_edi_token_expiry > datetime.now():
            return credentials_company.l10n_vn_edi_token_type, credentials_company.l10n_vn_edi_token, ""
       
        # tạm thời thay đổi GX
        #data = {'username': credentials_company.l10n_vn_edi_username, 'password': credentials_company.l10n_vn_edi_password}
        data = {
            'grant_type': 'client_credentials',
            'client_id': credentials_company.client_id,
            'client_secret': credentials_company.client_secret,
            'scope': scope_type
        }
       
        request_response, error_message = _l10n_vn_edi_send_request(
            method='POST',
            url= f"{e_invoice_API_URL}oauth/token",  # This one is special and uses another base address.
            form_data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
      
        if error_message:
            return "", error_message
        if 'access_token' not in request_response:  # Just in case something else go wrong and it's missing the token
            return "", _('Connection to the API failed, please try again later.')
        
        token_type = request_response['token_type']
        access_token = request_response['access_token']
       
        try:
            access_token_expiry = datetime.now() + timedelta(seconds=int(request_response['expires_in']))
        except ValueError:  # Simple security measure in case we don't get the expected format in the response.
            return "", _('Error while parsing API answer. Please try again later.')
       
        # Tokens are valid for 5 minutes. Storing it helps reduce api calls and speed up things a little bit.
        if scope_type == 'create-invoice':
            credentials_company.write({
                'l10n_vn_edi_token_type': token_type,
                'l10n_vn_edi_token': access_token,
                'l10n_vn_edi_token_expiry': access_token_expiry,
            })
       
        return token_type, access_token, ""

    def _l10n_vn_edi_get_credentials_company(self):
        """ The company holding the credentials could be one of the parent companies.
        We need to ensure that:
            - We use the credentials of the parent company, if no credentials are set on the child one.
            - We store the access token on the appropriate company, based on which holds the credentials.
        """

        # Chuyển đổi không dùng user và password -> client_id và client_secret
        # tạm thời thay đổi GX
        # if self.company_id.l10n_vn_edi_username and self.company_id.l10n_vn_edi_password:
        #     return self.company_id

        # return self.company_id.sudo().parent_ids.filtered(
        #     lambda c: c.l10n_vn_edi_username and c.l10n_vn_edi_password
        # )[-1:]

        if self.company_id.client_id and self.company_id.client_secret:
            return self.company_id

        return self.company_id.sudo().parent_ids.filtered(
            lambda c: c.client_id and c.client_secret
        )[-1:]

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_vn_edi_format_date(self, date):
        """
        All APIs for e_invoice uses the same time format, being the current hour, minutes and seconds converted into
        seconds since unix epoch, but formatting like milliseconds since unix epoch.
        It means that the time will end in 000 for the milliseconds as they are not as of today used by the system.
        """
        return int(date.timestamp()) * 1000 if date else 0

    @api.model
    def _l10n_vn_edi_format_phone_number(self, number):
        """
        Simple helper that takes in a phone number and try to format it to fit e_invoice format.
        e_invoice only allows digits, so we will remove any (, ), -, + characters.
        """
        # We first replace + by 00, then we remove all non digit characters.
        number = number.replace('+', '00')
        return re.sub(r'[^0-9]+', '', number)

    def _l10n_vn_edi_is_sent(self):
        """ Small helper that returns true if self has been sent to e_invoice. """
        self.ensure_one()
        sent_statuses = {'send', 'payment_state_to_update', 'canceled', 'adjusted', 'replaced'}
        return self.l10n_vn_edi_invoice_state in sent_statuses

    def action_show_invoice(self):
        self.ensure_one()

        # Kiểm tra trạng thái hóa đơn đã gửi chưa
        if self.l10n_vn_edi_invoice_state != 'send':
            raise UserError(_("Hóa đơn chưa được gửi đến hệ thống"))
        
        # Gọi API lấy PDF từ web service
        pdf_data, error_msg = self._l10n_vn_edi_fetch_invoice_pdf_file_data()
        
        if error_msg:
            raise UserError(_("Không thể lấy file PDF: %s") % error_msg)
        
        # Tạo attachment tạm thời (nếu cần lưu lại)
        attachment = self.env['ir.attachment'].create({
            'name': pdf_data['name'],
            'datas': base64.b64encode(pdf_data['raw']),
            'res_model': self._name,
            'res_id': self.id,
            'res_field': False,
            'type': 'binary',
            'mimetype': 'application/pdf',
            'public': False,  # Để có thể truy cập từ bên ngoài
        })
        
        # Trả về action để mở file PDF trong tab mới
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=false',
            'target': 'new',
        }
    
    def action_sign_invoice(self):
        self.ensure_one()

        token_type, access_token, error = self._l10n_vn_edi_get_access_token(scope_type='create-invoice')
        if error:
                raise UserError(error)
        
        request_response, error_message = _l10n_vn_edi_send_request(
                method='POST',
                url=f'{e_invoice_API_URL}api/invoice/xml-sign',
                #json_data=invoice_json_data,
                headers={'authorization':f"{token_type} {access_token}",
                         'Content-Type': 'application/json'},
            )
        
    def action_delete_invoice(self):
        """ Action to delete the invoice on e_invoice. """
        self.ensure_one()

        # Kiểm tra trạng thái hóa đơn đã gửi chưa
        if self.l10n_vn_edi_invoice_state != 'send':
            raise UserError(_("Hóa đơn chưa được gửi đến hệ thống"))
        
        token_type, access_token, error = self._l10n_vn_edi_get_access_token(scope_type='create-invoice')
        if error:
                raise UserError(error)
        
        # Kiểm tra HD này có id_attr chưa và gọi API lấy PDF từ web service
        if self.invoice_id_attr:
           files_data, error_message = self._l10n_vn_edi_try_fetch_invoice_file_data()
        if error_message:
                raise UserError(error)
        
        if files_data['data']['trangthai'] == 0:
           request_response, error_message = _l10n_vn_edi_send_request(
                method='POST',
                url=f'{e_invoice_API_URL}api/invoice/delete',
                json_data={
                    'id_attr': self.invoice_id_attr
                },
                #json_data=invoice_json_data,
                headers={'authorization':f"{token_type} {access_token}",
                         'Content-Type': 'application/json'},
            )
        
        if error_message:
           raise UserError('Lỗi không gửi được: %s', error)
        if request_response.get('status') != 200:
           raise UserError(request_response.get('message'))
        else:
            self.l10n_vn_edi_invoice_state = 'ready_to_send'
            
                
        # == Lock ==
       
      
       
        