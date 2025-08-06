{# Part of Odoo. See LICENSE file for full copyright and licensing details.
 # Tên module
    'name': 'POS System - T4Tek',
    'version': '18.0',

    # Loại module
    'category': 'Bank and POS',


    # Độ ưu tiên module trong list module
    # Số càng nhỏ, độ ưu tiên càng cao
    #### Chấp nhận số âm
    #'sequence': 5,

    # Mô tả module
    "summary": "Debt recording system and payment call",
    'description': 'Hệ thống ghi chép công nợ và gọi thanh toán',
    'author': 'GinGa GX',

    "depends": [
        "base"
    ],
    
    
    "data": [
        'security/access_user.xml',
        'security/ir.model.access.csv',
        'views/pos_category.xml',
        'views/invoice_report.xml',
        'views/wallet_contact.xml',
        'data/cron_invoice.xml',
        'views/menu_item.xml',
       
        
        
    ],

    'assets': {
        'web.assets_backend':
        [
            'pos_system/static/src/js/**/*',
            'pos_system/static/src/xml/**/*',
        ],
#         
    },
    "installable": True,
    "license": "LGPL-3",
}
