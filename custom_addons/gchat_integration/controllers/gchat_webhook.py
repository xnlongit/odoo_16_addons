# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import base64
import logging
import urllib.parse
import requests
from werkzeug.exceptions import Unauthorized, BadRequest
from odoo import fields
from datetime import timedelta

_logger = logging.getLogger(__name__)


class GchatWebhookController(http.Controller):
    
    @http.route('/gchat/webhook', auth='none', type='json', csrf=False, methods=['POST'])
    def gchat_webhook(self, **kwargs):
        """
        Webhook endpoint for Google Chat events.
        
        Expected payload format:
        {
            "message_id": "123456789",
            "publish_time": "2023-01-01T00:00:00Z",
            "attributes": {"key": "value"},
            "data_base64": "base64_encoded_event_data"
        }
        
        Returns:
            str: "OK" on success
        """
        try:
            # Get request data
            data = request.jsonrequest
            if not data:
                _logger.error("No JSON data received in webhook")
                raise BadRequest("No JSON data received")
            
            # Verify webhook token
            auth_header = request.httprequest.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                _logger.error("Missing or invalid Authorization header")
                raise Unauthorized("Missing or invalid Authorization header")
            
            token = auth_header.split(' ')[1]
            
            # Find configuration with matching webhook token
            config = request.env['gchat.config'].sudo().search([
                ('webhook_token', '=', token),
                ('is_active', '=', True)
            ], limit=1)
            
            if not config:
                _logger.error(f"Invalid webhook token: {token}")
                raise Unauthorized("Invalid webhook token")
            
            # Extract event data
            message_id = data.get('message_id')
            publish_time = data.get('publish_time')
            attributes = data.get('attributes', {})
            data_base64 = data.get('data_base64')
            
            if not message_id or not data_base64:
                _logger.error("Missing required fields: message_id or data_base64")
                raise BadRequest("Missing required fields")
            
            # Decode base64 data
            try:
                event_data = base64.b64decode(data_base64).decode('utf-8')
                event_json = json.loads(event_data)
            except Exception as e:
                _logger.error(f"Failed to decode event data: {str(e)}")
                raise BadRequest("Invalid event data format")
            
            # Create event log record
            event_log = request.env['gchat.event.log'].sudo().create({
                'external_event_id': message_id,
                'source': 'chat',
                'event_type': event_json.get('eventType', 'UNKNOWN'),
                'payload_json': json.dumps(event_json, indent=2),
                'status': 'new'
            })
            
            # Process the event
            envelope = {
                'message_id': message_id,
                'publish_time': publish_time,
                'attributes': attributes
            }
            
            success = event_log.process_incoming(envelope, event_json)
            
            if success:
                _logger.info(f"Successfully processed event {message_id}")
                return "OK"
            else:
                _logger.error(f"Failed to process event {message_id}")
                return "ERROR"
                
        except Unauthorized:
            _logger.error("Unauthorized webhook request")
            return "UNAUTHORIZED", 401
        except BadRequest as e:
            _logger.error(f"Bad request in webhook: {str(e)}")
            return "BAD_REQUEST", 400
        except Exception as e:
            _logger.error(f"Unexpected error in webhook: {str(e)}")
            return "INTERNAL_ERROR", 500

    @http.route('/gchat/oauth/callback', auth='public', type='http', methods=['GET'])
    def gchat_oauth_callback(self, **kwargs):
        """
        OAuth callback endpoint for Google Chat authentication.
        """
        try:
            code = kwargs.get('code')
            state = kwargs.get('state')
            error = kwargs.get('error')
            
            if error:
                return f"""
                <html>
                <body>
                    <h2>Lỗi xác thực Google</h2>
                    <p>Lỗi: {error}</p>
                    <p><a href="/web">Quay lại Odoo</a></p>
                </body>
                </html>
                """
            
            if not code:
                return """
                <html>
                <body>
                    <h2>Lỗi xác thực</h2>
                    <p>Không nhận được mã xác thực từ Google.</p>
                    <p><a href="/web">Quay lại Odoo</a></p>
                </body>
                </html>
                """
            
            # Tìm config để lưu token
            config = request.env['gchat.config'].sudo().search([
                ('is_active', '=', True)
            ], limit=1)
            
            if not config:
                return """
                <html>
                <body>
                    <h2>Lỗi cấu hình</h2>
                    <p>Không tìm thấy cấu hình Google Chat.</p>
                    <p><a href="/web">Quay lại Odoo</a></p>
                </body>
                </html>
                """
            
            # Lấy redirect URI
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            redirect_uri = base_url.rstrip('/') + '/gchat/oauth/callback'
            
            # Đổi code lấy token
            token_data = {
                'code': code,
                'client_id': config.oauth_client_id,
                'client_secret': config.oauth_client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            token_response = requests.post('https://oauth2.googleapis.com/token', data=token_data)
            token_info = token_response.json()
            
            if 'error' in token_info:
                return f"""
                <html>
                <body>
                    <h2>Lỗi lấy token</h2>
                    <p>Lỗi: {token_info.get('error_description', token_info.get('error'))}</p>
                    <p><a href="/web">Quay lại Odoo</a></p>
                </body>
                </html>
                """
            
            # Lưu token vào config
            config.write({
                'access_token': token_info.get('access_token'),
                'refresh_token': token_info.get('refresh_token'),
                'token_expiry': fields.Datetime.now() + timedelta(seconds=token_info.get('expires_in', 3600))
            })
            
            return """
            <html>
            <body>
                <h2>Xác thực thành công!</h2>
                <p>Đã lưu token Google Chat thành công.</p>
                <p>Bây giờ bạn có thể:</p>
                <ul>
                    <li>Gửi DM với cardsV2</li>
                    <li>Tạo và quản lý spaces</li>
                    <li>Gửi thông báo khi task thay đổi stage</li>
                </ul>
                <p><a href="/web">Quay lại Odoo</a></p>
            </body>
            </html>
            """
            
        except Exception as e:
            _logger.error(f"OAuth callback error: {str(e)}")
            return f"""
            <html>
            <body>
                <h2>Lỗi xử lý</h2>
                <p>Lỗi: {str(e)}</p>
                <p><a href="/web">Quay lại Odoo</a></p>
            </body>
            </html>
            """

    @http.route('/gchat/webhook/health', auth='none', type='http', methods=['GET'])
    def webhook_health(self, **kwargs):
        """
        Health check endpoint for webhook.
        
        Returns:
            str: Health status
        """
        try:
            # Check if any active configuration exists
            config_count = request.env['gchat.config'].sudo().search_count([
                ('is_active', '=', True)
            ])
            
            return json.dumps({
                'status': 'healthy',
                'active_configs': config_count,
                'timestamp': request.env['gchat.event.log'].sudo().search([], order='create_date desc', limit=1).create_date.isoformat() if request.env['gchat.event.log'].sudo().search_count([]) > 0 else None
            })
            
        except Exception as e:
            _logger.error(f"Health check failed: {str(e)}")
            return json.dumps({
                'status': 'unhealthy',
                'error': str(e)
            }), 500 