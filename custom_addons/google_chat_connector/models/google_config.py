# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import urllib.parse

class GoogleConfig(models.Model):
    _name = 'google.chat.config'
    _description = 'Google Chat Configuration'

    name = fields.Char('Configuration Name', required=True)
    client_id = fields.Char('Client ID', required=True)
    client_secret = fields.Char('Client Secret', required=True)
    access_token = fields.Char('Access Token')
    refresh_token = fields.Char('Refresh Token')
    token_expiry = fields.Datetime('Token Expiry')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)

    def action_test_connection(self):
        # Gửi request test đến Google, trả về notification
        pass

    def action_get_token(self):
        # Mở wizard hướng dẫn lấy token
        pass

    def test_connect(self):
        """
        Kiểm tra client_id và client_secret bằng cách gọi endpoint token với code giả.
        Nếu trả về lỗi 'invalid_grant' là hợp lệ, nếu trả về 'invalid_client' là sai.
        """
        self.ensure_one()
        url = 'https://oauth2.googleapis.com/token'
        data = {
            'code': 'dummy_code',  # code giả
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': 'https://localhost',  # hoặc redirect_uri thực tế nếu có
            'grant_type': 'authorization_code',
        }
        try:
            resp = requests.post(url, data=data, timeout=10)
            result = resp.json()
            error = result.get('error')
            if error == 'invalid_grant':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Thành công',
                        'message': 'Client ID và Secret hợp lệ (Google trả về invalid_grant do code giả, nhưng thông tin hợp lệ).',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            elif error == 'invalid_client':
                raise UserError(_('Client ID hoặc Secret không hợp lệ!'))
            else:
                raise UserError(_('Lỗi: %s') % result)
        except Exception as e:
            raise UserError(_('Lỗi kết nối: %s') % str(e))

    def action_login_google(self):
        self.ensure_one()
        client_id = self.client_id
        redirect_uri = self._get_redirect_uri()
        # Thêm scope chat.bot
        scope = 'openid email profile https://www.googleapis.com/auth/chat.messages'
        state = 'test_state'
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
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

    def _get_redirect_uri(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return base_url.rstrip('/') + '/google_oauth_callback'

    def send_message_to_space(self, message, space_id):
        self.ensure_one()
        if not self.access_token:
            raise UserError("Chưa có access_token, hãy xác thực Google trước.")
        url = f"https://chat.googleapis.com/v1/spaces/{space_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "text": message
        }
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 200:
            return resp.json()
        else:
            raise UserError(f"Lỗi gửi message: {resp.status_code} - {resp.text}")

    def send_notification(self, model, event, record):
        mapping = self.env['google.chat.mapping'].search([
            ('model_id.model', '=', model),
            ('event_type', '=', event),
            ('active', '=', True)
        ], limit=1)
        if mapping:
            template = mapping.template_id
            message = template.render_template(template.body_html, model, record.id)
            self.send_message_to_space(message, mapping.space_id)
            # Ghi log
            self.env['google.chat.log'].create({
                'config_id': self.id,
                'message': message,
                'space_id': mapping.space_id,
                'status': 'success',
                'user_id': self.env.user.id,
            })