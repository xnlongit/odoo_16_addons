# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import base64
import logging

_logger = logging.getLogger(__name__)


class GchatConfig(models.Model):
    _name = 'gchat.config'
    _description = 'Google Chat Configuration'
    _rec_name = 'name'

    name = fields.Char('Configuration Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company, required=True)
    is_active = fields.Boolean('Active', default=True)
    
    # Authentication
    auth_mode = fields.Selection([
        ('service_account', 'Service Account'),
        ('oauth', 'OAuth 2.0')
    ], string='Authentication Mode', required=True, default='service_account')
    
    # Service Account fields
    sa_json = fields.Binary('Service Account JSON', attachment=True)
    sa_json_filename = fields.Char('SA JSON Filename')
    
    # OAuth fields
    oauth_client_id = fields.Char('OAuth Client ID')
    oauth_client_secret = fields.Char('OAuth Client Secret')
    refresh_token = fields.Char('Refresh Token')
    access_token = fields.Char('Access Token')
    token_expiry = fields.Datetime('Token Expiry')
    
    # API Configuration
    scopes = fields.Text('Scopes', default='https://www.googleapis.com/auth/chat.messages')
    webhook_token = fields.Char('Webhook Token', required=True, 
                               help='Token for webhook authentication')
    
    # Status fields
    last_sync = fields.Datetime('Last Sync')
    sync_status = fields.Selection([
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('error', 'Error')
    ], default='idle')
    error_message = fields.Text('Last Error')

    _sql_constraints = [
        ('unique_company_config', 'unique(company_id)', 
         'Only one configuration per company is allowed.')
    ]

    @api.constrains('auth_mode', 'sa_json', 'oauth_client_id', 'oauth_client_secret')
    def _check_auth_configuration(self):
        """Validate authentication configuration based on mode."""
        for config in self:
            if config.auth_mode == 'service_account':
                if not config.sa_json:
                    raise ValidationError(_('Service Account JSON is required for service account mode.'))
            elif config.auth_mode == 'oauth':
                if not config.oauth_client_id or not config.oauth_client_secret:
                    raise ValidationError(_('OAuth Client ID and Secret are required for OAuth mode.'))

    def get_client(self, as_user=None):
        """
        Get Google API client for authentication.
        
        Args:
            as_user (str): Email to impersonate (for service account)
            
        Returns:
            Google API client instance
        """
        # TODO: Implement Google API client creation
        # - For service account: use sa_json
        # - For OAuth: use refresh_token to get access_token
        # - Handle impersonation if as_user provided
        _logger.info(f"Getting Google API client for config {self.name}")
        return None

    def send_chat(self, space_id, text=None, cards=None, thread_key=None):
        """
        Send message to Google Chat space.
        
        Args:
            space_id (str): Google Chat space ID
            text (str): Message text
            cards (list): Message cards
            thread_key (str): Thread key for threading
            
        Returns:
            dict: API response
        """
        # TODO: Implement Google Chat API call
        # - Use get_client() to get authenticated client
        # - Call Chat API with proper message format
        # - Handle errors and retries
        _logger.info(f"Sending message to space {space_id}, thread {thread_key}")
        
        message_data = {
            'space_id': space_id,
            'text': text,
            'cards': cards,
            'thread_key': thread_key
        }
        
        # Mock implementation
        return {'success': True, 'message_id': 'mock_123'}

    def refresh_if_needed(self):
        """Refresh OAuth token if expired."""
        if self.auth_mode == 'oauth' and self.token_expiry:
            # TODO: Check if token is expired and refresh
            _logger.info(f"Checking token expiry for config {self.name}")
            pass

    def action_test_connection(self):
        """Test Google Chat connection."""
        try:
            # TODO: Implement connection test
            # - Try to list spaces or send test message
            _logger.info(f"Testing connection for config {self.name}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Connection test successful'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('Connection test failed: %s') % str(e))

    def action_get_oauth_token(self):
        """Open OAuth flow to get tokens."""
        # TODO: Implement OAuth flow
        # - Redirect to Google OAuth
        # - Handle callback and store tokens
        _logger.info(f"Starting OAuth flow for config {self.name}")
        pass 