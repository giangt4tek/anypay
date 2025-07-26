{# Part of Odoo. See LICENSE file for full copyright and licensing details.
 # Tên module
    'name': 'Visual AnyPay-Wallet - T4Tek',
    'version': '18.0',

    # Loại module
    'category': 'Wallet and POS',


    # Độ ưu tiên module trong list module
    # Số càng nhỏ, độ ưu tiên càng cao
    #### Chấp nhận số âm
    'sequence': 5,

    # Mô tả module
    "summary": "Visual Walleting system by T4Tek",
    'description': 'Hệ thống Ví AnyPay trực quan của T4Tek',
    'author': 'GinGa GX',

    "depends": [
        "base","account"
    ],
    
    
    "data": [
        'security/access_user.xml',
        'security/ir.model.access.csv',
        'views/t4tek_wallet_account_view.xml',
        'views/transaction_report.xml',
        'views/invoice_report.xml',
        'views/res_partner_inherit.xml',
        'views/wallet_contact.xml',
        'views/res_partner_view.xml',
        # 'data/cron_invoice.xml',
        'views/menu_item.xml',
        
        
    ],

    'assets': {
        'web.assets_backend':
        [
            'anypay_wallet/static/src/js/**/*',
            'anypay_wallet/static/src/xml/**/*',
        ],
#         
    },
    "installable": True,
    "license": "LGPL-3",
}
