# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import base64
import logging
import urllib.parse
import requests
from datetime import timedelta
from dateutil.relativedelta import relativedelta

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
    ], string='Authentication Mode', required=True, default='oauth')
    
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
    scopes = fields.Text('Scopes', default='https://www.googleapis.com/auth/chat.messages.create https://www.googleapis.com/auth/chat.spaces.readonly')
    webhook_token = fields.Char('Webhook Token', 
                               help='Token for webhook authentication (optional for OAuth mode)')
    
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

    def _base_url(self):
        """Return base URL for Google Chat API."""
        return "https://chat.googleapis.com/v1"

    def _headers(self):
        """Return headers for API requests."""
        return {
            "Authorization": f"Bearer {self._ensure_access_token()}",
            "Content-Type": "application/json",
            "User-Agent": "Odoo-GChat/1.0",
        }

    def _ensure_access_token(self):
        """Return valid access_token; refresh if expired (<= 5 min)."""
        self.ensure_one()
        if not self.access_token or self._is_expired():
            self._refresh_token()
        return self.access_token

    def _is_expired(self):
        """Check if token is expired (with 5 min safety margin)."""
        if not self.token_expiry:
            return True
        # an toàn: trừ 5 phút
        return fields.Datetime.now() >= (self.token_expiry - relativedelta(minutes=5))

    def _refresh_token(self):
        """OAuth refresh_token → access_token."""
        self.ensure_one()
        if not self.refresh_token:
            raise UserError(_('No refresh token available. Please re-authenticate with Google.'))
        
        data = {
            "client_id": self.oauth_client_id,
            "client_secret": self.oauth_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        
        try:
            r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=20)
            r.raise_for_status()
            tok = r.json()
            
            self.sudo().write({
                "access_token": tok.get("access_token"),
                "token_expiry": fields.Datetime.now() + relativedelta(seconds=int(tok.get("expires_in", 3600))),
            })
            
            _logger.info(f"Token refreshed successfully for config {self.name}")
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to refresh token: {str(e)}"
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail.get('error_description', error_detail.get('error', 'Unknown error'))}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            
            _logger.error(error_msg)
            raise UserError(error_msg)

    def _request(self, method, url, json_payload=None, retry_on_401=True):
        """Make HTTP request with automatic token refresh on 401."""
        self.ensure_one()
        
        headers = self._headers()
        
        try:
            r = requests.request(method, url, headers=headers, json=json_payload, timeout=30)
            
            if r.status_code == 401 and retry_on_401:
                # refresh & retry once
                _logger.info(f"Token expired, refreshing and retrying request to {url}")
                self._refresh_token()
                headers = self._headers()
                r = requests.request(method, url, headers=headers, json=json_payload, timeout=30)
            
            # raise for non-2xx
            if r.status_code // 100 != 2:
                error_msg = f"GChat API {r.status_code}: {r.text[:500]}"
                _logger.error(f"API request failed: {error_msg}")
                raise UserError(error_msg)
            
            return r.json() if r.text else {}
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg)

    def find_or_create_dm(self, user_identifier):
        """
        Find or create DM space with user.
        
        Args:
            user_identifier: email 'user@company.com' hoặc 'users/123456789'
            
        Returns:
            str: Space ID in format 'spaces/AAAA...'
        """
        self.ensure_one()
        
        base = self._base_url()
        # nếu là email: cần URL-encode. name='users/{email}'
        from urllib.parse import quote
        name = f"users/{quote(user_identifier)}" if "@" in user_identifier else user_identifier
        url = f"{base}/spaces:findDirectMessage?name={name}"
        
        try:
            resp = self._request("GET", url)
            # resp.name là 'spaces/AAAA...'
            space_id = resp.get("name")
            if space_id:
                _logger.info(f"Found DM space {space_id} for user {user_identifier}")
                return space_id
            else:
                raise UserError(f"Could not find or create DM space for user {user_identifier}")
                
        except Exception as e:
            _logger.error(f"Failed to find/create DM for user {user_identifier}: {str(e)}")
            raise

    def send_card_dm(self, space_id, *, title, subtitle=None, items=None, button_text=None, button_url=None, thread_key=None):
        """
        Send cardsV2 message to DM space.
        
        Args:
            space_id (str): Space ID in format 'spaces/AAAA...'
            title (str): Card title
            subtitle (str): Card subtitle (optional)
            items (list): List of text items to display
            button_text (str): Button text (optional)
            button_url (str): Button URL (optional)
            thread_key (str): Thread key for threading (optional)
            
        Returns:
            dict: API response
        """
        self.ensure_one()
        
        base = self._base_url()
        url = f"{base}/{space_id}/messages"

        card_widgets = []
        
        # items
        for it in (items or []):
            card_widgets.append({"decoratedText": {"text": it}})
        
        # button
        if button_text and button_url:
            card_widgets.append({
                "buttonList": {
                    "buttons": [{
                        "text": button_text,
                        "onClick": {"openLink": {"url": button_url}}
                    }]
                }
            })

        card = {
            "cardId": "odoo_notify",
            "card": {
                "header": { 
                    "title": title, 
                    **({"subtitle": subtitle} if subtitle else {}) 
                },
                "sections": [{ 
                    "widgets": card_widgets or [{"decoratedText": {"text": " "}}] 
                }]
            }
        }

        body = {
            "text": title,
            "cardsV2": [card],
        }
        
        if thread_key:
            body["thread"] = {"threadKey": str(thread_key)}

        try:
            resp = self._request("POST", url, json_payload=body)
            _logger.info(f"Card message sent successfully to {space_id}")
            return resp
            
        except Exception as e:
            _logger.error(f"Failed to send card message to {space_id}: {str(e)}")
            raise

    def send_card_to_user(self, user_email, **kwargs):
        """
        Send card message to user via DM.
        
        Args:
            user_email (str): User email address
            **kwargs: Arguments for send_card_dm
            
        Returns:
            dict: API response
        """
        self.ensure_one()
        
        space_id = self.find_or_create_dm(user_email)
        if not space_id:
            raise UserError("Không tìm thấy hoặc tạo được DM space cho user này.")
        
        return self.send_card_dm(space_id, **kwargs)

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
        self.ensure_one()
        
        if not self.access_token:
            raise UserError(_('Access token not found. Please authenticate with Google first.'))
        
        # Refresh token if needed
        self.refresh_if_needed()
        
        # Prepare message data
        message_data = {}
        
        if text:
            message_data['text'] = text
        
        if cards:
            message_data['cards'] = cards
        
        # Add thread key only for service account (not for OAuth user)
        if thread_key and self.auth_mode == 'service_account':
            message_data['threadKey'] = thread_key
        
        if not message_data:
            raise UserError(_('Message must contain either text or cards.'))
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Send message
        url = f'https://chat.googleapis.com/v1/spaces/{space_id}/messages'
        
        try:
            response = requests.post(url, headers=headers, json=message_data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            _logger.info(f"Message sent successfully to space {space_id}: {result.get('name', 'Unknown')}")
            
            return {
                'success': True,
                'message_id': result.get('name', ''),
                'response': result
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to send message to Google Chat: {str(e)}"
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail.get('error', {}).get('message', 'Unknown error')}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            
            _logger.error(error_msg)
            raise UserError(error_msg)

    def list_spaces(self):
        """
        List available Google Chat spaces.
        
        Returns:
            list: List of space information
        """
        self.ensure_one()
        
        if not self.access_token:
            raise UserError(_('Access token not found. Please authenticate with Google first.'))
        
        # Refresh token if needed
        self.refresh_if_needed()
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        url = 'https://chat.googleapis.com/v1/spaces'
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            spaces = result.get('spaces', [])
            
            _logger.info(f"Retrieved {len(spaces)} spaces from Google Chat")
            
            return spaces
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to list Google Chat spaces: {str(e)}"
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail.get('error', {}).get('message', 'Unknown error')}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            
            _logger.error(error_msg)
            raise UserError(error_msg)

    def create_space(self, display_name, description=None):
        """
        Create a new Google Chat space.
        
        Args:
            display_name (str): Space display name
            description (str): Space description
            
        Returns:
            dict: Created space information
        """
        self.ensure_one()
        
        if not self.access_token:
            raise UserError(_('Access token not found. Please authenticate with Google first.'))
        
        # Refresh token if needed
        self.refresh_if_needed()
        
        # Prepare space data
        space_data = {
            'displayName': display_name,
            'type': 'ROOM'
        }
        
        if description:
            space_data['description'] = description
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        url = 'https://chat.googleapis.com/v1/spaces'
        
        try:
            response = requests.post(url, headers=headers, json=space_data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            _logger.info(f"Space created successfully: {result.get('name', 'Unknown')}")
            
            return {
                'success': True,
                'space_id': result.get('name', ''),
                'display_name': result.get('displayName', ''),
                'type': result.get('type', ''),
                'response': result
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to create Google Chat space: {str(e)}"
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail.get('error', {}).get('message', 'Unknown error')}"
                except:
                    error_msg += f" - Status: {e.response.status_code}"
            
            _logger.error(error_msg)
            raise UserError(error_msg)

    def refresh_if_needed(self):
        """Refresh OAuth token if expired."""
        if self.auth_mode == 'oauth' and self.token_expiry:
            # TODO: Check if token is expired and refresh
            _logger.info(f"Checking token expiry for config {self.name}")
            pass

    def action_test_connection(self):
        """Test Google Chat connection."""
        try:
            # Test by listing spaces
            spaces = self.list_spaces()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Connection test successful. Found %d spaces.') % len(spaces),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('Connection test failed: %s') % str(e))

    def action_list_spaces(self):
        """List available Google Chat spaces."""
        try:
            spaces = self.list_spaces()
            
            # Create a simple list for display
            space_list = []
            for space in spaces:
                space_list.append({
                    'name': space.get('displayName', 'Unknown'),
                    'space_id': space.get('name', ''),
                    'type': space.get('type', ''),
                    'description': space.get('description', '')
                })
            
            # Return as notification with space count
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Available Spaces'),
                    'message': _('Found %d spaces. Check logs for details.') % len(spaces),
                    'type': 'info',
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to list spaces: %s') % str(e))

    def action_get_oauth_token(self):
        """Open OAuth flow to get tokens."""
        self.ensure_one()
        
        if not self.oauth_client_id:
            raise UserError(_('OAuth Client ID is required. Please configure it first.'))
        
        # Lấy base URL của Odoo
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = base_url.rstrip('/') + '/gchat/oauth/callback'
        
        # Tạo OAuth URL
        oauth_params = {
            'client_id': self.oauth_client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': self.scopes or 'https://www.googleapis.com/auth/chat.messages.create https://www.googleapis.com/auth/chat.spaces.readonly',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': f'config_{self.id}'
        }
        
        oauth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(oauth_params)
        
        return {
            'type': 'ir.actions.act_url',
            'url': oauth_url,
            'target': 'self',
        } 