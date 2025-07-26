from odoo import models, fields, api
import uuid
import logging
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    cccd = fields.Char(string="CCCD", required=False)
    _sql_constraints = [ ('unique_cccd', 'unique(cccd)', 'Mỗi CCCD chỉ được gán cho 1 khách hàng!')]

    balance_amount = fields.Monetary(
    string="Số dư",
    currency_field="currency_id",
    default=0.0)



    # def _action_dashboard(self):
    #     user = self.env.user

    #     if user.has_group('anypay_wallet.user_wallet'):
    #         action = {
    #             'type': 'ir.actions.client',
    #             'tag': 'anypay_wallet.transaction_dashboard',
    #         }
    #         return action
    def _action_dashboard(self):
        user = self.env.user
        if user.has_group('anypay_wallet.manager_wallet'):
           context = {'create': False, 'edit': True, 'delete': False},
           view_kanban_id = self.env.ref('base.res_partner_kanban_view').id
           view_list_id = self.env.ref('base.view_partner_tree').id
           view_form_id = self.env.ref(
               'anypay_wallet.form_view_res_partner').id
           action = {
               'type': 'ir.actions.act_window',
               'res_model': 'res.partner',
           }
           action.update({
               'name': 'Partner',
               'view_mode': 'kanban,list,form',
               'views': [[view_kanban_id, 'kanban'], [view_list_id, 'list'], [view_form_id, 'form']],
               
               'context': context
           })
           return action
        elif user.has_group('anypay_wallet.user_wallet'):
            action = {
                'type': 'ir.actions.client',
                'tag': 'anypay_wallet.transaction_dashboard',
            }
            return action

    def _action_dashboard_manager(self):
        context = {}
        
        if self.env.user.has_group('anypay_wallet.manager_wallet'):
            context = {'create': False, 'edit': True, 'delete': False},
    
        view_kanban_id = self.env.ref('base.res_partner_kanban_view').id
        view_list_id = self.env.ref('base.view_partner_list').id
        view_form_id = self.env.ref(
            'anypay_wallet.form_view_res_partner_manager').id
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
        }
        action.update({
            'name': 'Partner',
            'view_mode': 'kanban,list,form',
            'views': [[view_kanban_id, 'kanban'], [view_list_id, 'list'], [view_form_id, 'form']],
           
            'context': context
        })

        return action