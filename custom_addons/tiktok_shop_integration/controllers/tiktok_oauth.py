from odoo import http
from odoo.http import request
from odoo.addons.google_chat_connector.models.google_config import GoogleConfig
import urllib.parse
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class TiktokOAuthController(http.Controller):
    @http.route('/tiktok_oauth_callback', type='http', auth='public', csrf=False)
    def tiktok_oauth_callback(self, **kwargs):
        """
        Callback từ TikTok sẽ về:
        https://odoo.website/tiktok_oauth_callback?code=AUTHORIZATION_CODE&state=...
        """
        app_key = request.env['ir.config_parameter'].sudo().get_param('tiktok.app_key')
        app_secret = request.env['ir.config_parameter'].sudo().get_param('tiktok.app_secret')

        code = kwargs.get('code')
        state = kwargs.get('state')

        if not code:
            return request.make_response("Missing 'code' in callback", headers=[('Content-Type', 'text/plain')],
                                         status=400)

        try:
            # Theo Authorization overview mới của TikTok Shop:
            # GET https://auth.tiktok-shops.com/api/v2/token/get?app_key=...&app_secret=...&auth_code=...&grant_type=authorized_code
            # (Nếu doc của bạn yêu cầu POST JSON thì đổi sang requests.post và data/json tương ứng)
            token_url = 'https://auth.tiktok-shops.com/api/v2/token/get'  # doc OAuth 202407 nêu endpoint này. :contentReference[oaicite:0]{index=0}
            params = {
                'app_key': app_key,
                'app_secret': app_secret,
                'auth_code': code,
                'grant_type': 'authorized_code',
            }
            resp = requests.get(token_url, params=params, timeout=20)
            data = {}
            try:
                data = resp.json()
            except Exception:
                pass

            if resp.status_code != 200 or not data or data.get('code') not in (0, '0'):
                _logger.error("TikTok token exchange failed: status=%s body=%s", resp.status_code, resp.text)
                return request.make_response("Token exchange failed. Check logs.",
                                             headers=[('Content-Type', 'text/plain')], status=400)

            access_token = data['data']['access_token']
            refresh_token = data['data'].get('refresh_token')
            expires_in = data['data'].get('expires_in')

            # Lưu vào ir.config_parameter (hoặc model riêng của bạn)
            icp = request.env['ir.config_parameter'].sudo()
            icp.set_param('tiktok.access_token', access_token)
            if refresh_token:
                icp.set_param('tiktok.refresh_token', refresh_token)
            if expires_in:
                icp.set_param('tiktok.access_token_expires_in', str(expires_in))

            # Simple success page
            html = f"""
                    <html><body>
                        <h3>Authorized OK</h3>
                        <p>state: {state}</p>
                        <p>access_token has been saved.</p>
                    </body></html>
                """
            return request.make_response(html, headers=[('Content-Type', 'text/html')], status=200)

        except Exception as e:
            _logger.exception("Error in TikTok OAuth callback: %s", e)
            return request.make_response("Internal error", headers=[('Content-Type', 'text/plain')], status=500)
