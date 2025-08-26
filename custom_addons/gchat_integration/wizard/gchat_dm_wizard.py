# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class GchatDmWizard(models.TransientModel):
    _name = 'gchat.dm.wizard'
    _description = 'Send Google Chat DM Wizard'

    user_email = fields.Char('User Email', required=True, 
                            help='Email address of the user to send DM to')
    title = fields.Char('Title', required=True, 
                       help='Card title')
    subtitle = fields.Char('Subtitle', 
                          help='Card subtitle (optional)')
    items = fields.Text('Items', 
                       help='One item per line (optional)')
    button_text = fields.Char('Button Text', 
                             help='Button text (optional)')
    button_url = fields.Char('Button URL', 
                            help='Button URL (optional)')
    thread_key = fields.Char('Thread Key', 
                            help='Thread key for threading (optional)')
    
    # Configuration selection
    config_id = fields.Many2one('gchat.config', string='Configuration', 
                               domain=[('is_active', '=', True)], required=True)
    
    @api.model
    def default_get(self, fields_list):
        """Set default configuration."""
        res = super().default_get(fields_list)
        
        # Get default config for current company
        config = self.env['gchat.config'].search([
            ('company_id', '=', self.env.company.id),
            ('is_active', '=', True)
        ], limit=1)
        
        if config:
            res['config_id'] = config.id
        
        return res

    def action_send_dm(self):
        """Send DM to user."""
        self.ensure_one()
        
        try:
            # Parse items from text field
            items = []
            if self.items:
                items = [line.strip() for line in self.items.split('\n') if line.strip()]
            
            # Prepare kwargs for send_card_to_user
            kwargs = {
                'title': self.title,
                'items': items if items else None,
            }
            
            if self.subtitle:
                kwargs['subtitle'] = self.subtitle
            if self.button_text and self.button_url:
                kwargs['button_text'] = self.button_text
                kwargs['button_url'] = self.button_url
            if self.thread_key:
                kwargs['thread_key'] = self.thread_key
            
            # Send DM
            result = self.config_id.send_card_to_user(self.user_email, **kwargs)
            
            _logger.info(f"DM sent successfully to {self.user_email}: {result}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('DM sent successfully to %s') % self.user_email,
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Failed to send DM to {self.user_email}: {str(e)}")
            raise UserError(_('Failed to send DM: %s') % str(e))

    def action_test_dm(self):
        """Send test DM to current user."""
        self.ensure_one()
        
        # Set test values
        self.write({
            'user_email': self.env.user.email,
            'title': 'Test Notification from Odoo',
            'subtitle': 'This is a test message',
            'items': '📋 Test item 1\n📋 Test item 2\n📋 Test item 3',
            'button_text': 'Open Odoo',
            'button_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            'thread_key': 'test_thread'
        })
        
        return self.action_send_dm() 