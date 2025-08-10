{# Part of Odoo. See LICENSE file for full copyright and licensing details.
 # Tên module
    'name': 'E-invoice T4Tek',
    'version': '18.0',

    # Loại module
    'category': '1. MixDD POS',


    # Độ ưu tiên module trong list module
    # Số càng nhỏ, độ ưu tiên càng cao
    #### Chấp nhận số âm
    'sequence': 5,

    # Mô tả module
    "summary": "E-invoicing using PA by T4Tek",
    'description': '',
    'author': 'GinGa GX',

    "depends": [
        "base", "l10n_vn", "point_of_sale"
    ],
    
    
    "data": [
        'security/ir.model.access.csv',
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/e_invoice_views.xml",
        "wizard/account_move_reversal_view.xml",
        "wizard/account_move_send_wizard_view.xml",
        "wizard/l10n_vn_edi_cancellation_request_views.xml",
    ],

    'assets': {
        'web.assets_backend':
        [
            'e_invoice_t4tek/static/src/js/**/*',
            'e_invoice_t4tek/static/src/xml/**/*',
        ],
#         Nhóm tài nguyên này được sử dụng cho màn hình Point of Sale (POS) trong Odoo.
# Các tệp được liệt kê trong nhóm này sẽ được tải khi người dùng mở ứng dụng POS.
        'point_of_sale._assets_pos':[
            'e_invoice_t4tek/static/src/xml/pos/**/*',
            'e_invoice_t4tek/static/src/js/pos/**/*',
          
        ],
    },
    "installable": True,
    "license": "LGPL-3",
}
