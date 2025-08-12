# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import base64
import logging
from werkzeug.exceptions import Unauthorized, BadRequest

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