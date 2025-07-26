{# Part of Odoo. See LICENSE file for full copyright and licensing details.
 # Tên module
    'name': 'Visual Bank - T4Tek',
    'version': '18.0',

    # Loại module
    'category': 'Bank and POS',


    # Độ ưu tiên module trong list module
    # Số càng nhỏ, độ ưu tiên càng cao
    #### Chấp nhận số âm
    'sequence': 5,

    # Mô tả module
    "summary": "Visual banking system by T4Tek",
    'description': 'Hệ thống ngân hàng trực quan của T4Tek',
    'author': 'GinGa GX',

    "depends": [
        "base","account"
    ],
    
    
    "data": [
        'security/access_user.xml',
        'security/ir.model.access.csv',
        'views/t4tek_bank_account_view.xml',
        'views/transaction_report.xml',
        'views/invoice_report.xml',
        'views/res_partner_inherit.xml',
        'views/bank_contact.xml',
        'views/res_partner_view.xml',
        # 'data/cron_invoice.xml',
        'views/menu_item.xml',
        
        
    ],

    'assets': {
        'web.assets_backend':
        [
            'bank_server/static/src/js/**/*',
            'bank_server/static/src/xml/**/*',
        ],
#         
    },
    "installable": True,
    "license": "LGPL-3",
}
