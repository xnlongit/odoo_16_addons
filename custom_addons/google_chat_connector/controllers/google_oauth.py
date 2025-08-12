from odoo import http
from odoo.http import request
from odoo.addons.google_chat_connector.models.google_config import GoogleConfig
import urllib.parse
import requests
import json

class GoogleOAuthController(http.Controller):
    @http.route('/google_login', auth='public', type='http')
    def google_login(self, **kwargs):
        # Lấy client_id từ cấu hình
        config = request.env['google.config'].sudo().search([], limit=1)
        if not config:
            return 'Google OAuth chưa được cấu hình.'
        client_id = config.client_id
        redirect_uri = request.httprequest.host_url.rstrip('/') + '/google_oauth_callback'
        scope = 'openid email profile'
        state = 'test_state'  # Có thể random hoặc lưu session
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scope,
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent',
        }
        url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
        return request.redirect(url)

    @http.route('/google_oauth_callback', auth='public', type='http')
    def google_oauth_callback(self, **kwargs):
        code = kwargs.get('code')
        state = kwargs.get('state')
        if not code:
            return 'Không nhận được mã xác thực từ Google.'
        config = request.env['google.config'].sudo().search([], limit=1)
        if not config:
            return 'Chưa cấu hình Google OAuth.'
        # Lấy redirect_uri động, phải giống hệt khi tạo URL đăng nhập Google
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = base_url.rstrip('/') + '/google_oauth_callback'
        data = {
            'code': code,
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        token_res = requests.post('https://oauth2.googleapis.com/token', data=data)
        token_info = token_res.json()
        config.write({'access_token': token_info.get("access_token")})
        return """
            <h2>Đăng nhập Google thành công!</h2>
            <p>Access Token: {}</p>
            <pre>{}</pre>
        """.format(token_info.get("access_token"), token_info)

class GoogleChatWebhookController(http.Controller):
    @http.route('/google-chat/webhook', auth='public', type='json', csrf=False)
    def google_chat_webhook(self, **kwargs):
        data = json.loads(request.httprequest.data)
        config = request.env['google.config'].sudo().search([], limit=1)
        space_id = data.get('chat').get('messagePayload').get('space').get('name').split("/")[1]
        user_email = data.get('chat').get('user').get('email')
        if space_id and user_email:
            partner = request.env['res.partner'].sudo().search([('email', '=', user_email)], limit=1)
            if partner:
                partner.sudo().write({'space_id': space_id})
        return config.send_message_to_space("Khởi tạo thành công!", space_id)
