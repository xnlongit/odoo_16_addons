# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging, time, hmac, hashlib, requests
from datetime import datetime, timedelta
from urllib.parse import urlparse
import json

_logger = logging.getLogger(__name__)

OPENAPI_BASE = "https://open-api.tiktokglobalshop.com"
AUTH_BASE    = "https://auth.tiktok-shops.com"
DEFAULT_VER  = "202309"

class TiktokShopConfig(models.Model):
    _name = 'tiktok.shop.config'
    _description = 'Tiktok Shop Configuration'

    name = fields.Char('Configuration Name', required=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda s: s.env.company, required=True)
    is_active = fields.Boolean('Active', default=True)

    # OAuth
    app_key = fields.Char('OAuth Client ID')
    app_secret = fields.Char('OAuth Client Secret')
    version = fields.Char('Version', default=DEFAULT_VER)
    refresh_token = fields.Char('Refresh Token')
    access_token = fields.Char('Access Token')
    token_expiry = fields.Datetime('Token Expiry (UTC)')
    refresh_token_expiry = fields.Datetime('Refresh Token Expiry (UTC)')

    # Status
    last_sync = fields.Datetime('Last Sync')
    sync_status = fields.Selection([
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('error', 'Error')
    ], default='idle')
    error_message = fields.Text('Last Error')

    # ---------- Utils ----------
    def _ensure_conf(self):
        for rec in self:
            if not rec.app_key or not rec.app_secret:
                raise UserError(_("Thiếu app_key/app_secret."))
            if not rec.version:
                rec.version = DEFAULT_VER

    @api.model
    def _utcnow(self):
        return datetime.utcnow()

    def _generate_sign(self, request_option):
        self._ensure_conf()
        params = request_option.get('qs', {}) or {}
        exclude_keys = {"access_token", "sign"}
        sorted_items = [
            {"key": key, "value": params[key]}
            for key in sorted(params.keys())
            if key not in exclude_keys
        ]
        param_string = ''.join(f"{item['key']}{item['value']}" for item in sorted_items)

        uri = request_option.get('uri', '') or ''
        pathname = urlparse(uri).path if uri else ''
        sign_string = f"{pathname}{param_string}"

        content_type = (request_option.get('headers', {}) or {}).get('content-type', '')
        body = request_option.get('body', {}) or {}
        if content_type != 'multipart/form-data' and body:
            body_str = json.dumps(body, separators=(',', ':'), ensure_ascii=False)
            sign_string += body_str

        wrapped = f"{self.app_secret}{sign_string}{self.app_secret}"
        digest = hmac.new(
            self.app_secret.encode('utf-8'),
            wrapped.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return digest

    def _make_signed_params(self, path, extra_params=None, headers=None, body=None):
        if not path or not path.startswith('/'):
            raise UserError(_("Field 'Path' phải là endpoint, ví dụ: /authorization/202309/shops"))
        ts = int(time.time())
        qs = {
            "app_key": self.app_key,
            "timestamp": str(ts),
        }
        if extra_params:
            qs.update(extra_params)
        req_opt = {
            'qs': qs,
            'uri': path,
            'headers': headers or {"content-type": "application/json"},
            'body': body or {},
        }
        signature = self._generate_sign(req_opt)
        qs_with_sign = {**qs, 'sign': signature}
        return qs_with_sign

    def _headers(self, with_token=True, content_type="application/json"):
        headers = {"content-type": content_type}
        if with_token:
            if not self.access_token:
                raise UserError(_("Chưa có access_token. Hãy đổi code → token trước."))
            headers["x-tts-access-token"] = self.access_token
        return headers

    def _set_error(self, msg):
        self.write({'sync_status': 'error', 'error_message': msg})
        _logger.error("TikTok error: %s", msg)

    def api_request(self, method, path, query=None, body=None, with_token=True, content_type="application/json", timeout=30):
        self.ensure_one()
        self._ensure_conf()
        query = dict(query or {})
        body = body or {}
        headers = self._headers(with_token=with_token, content_type=content_type)

        signed_qs = self._make_signed_params(path, extra_params=query, headers=headers, body=body)
        url = f"{OPENAPI_BASE}{path}"

        try:
            if method.upper() == 'GET':
                resp = requests.get(url, params=signed_qs, headers=headers, timeout=timeout)
            elif method.upper() == 'POST':
                if content_type == 'multipart/form-data':
                    resp = requests.post(url, params=signed_qs, headers=headers, data=body, timeout=timeout)
                else:
                    resp = requests.post(url, params=signed_qs, headers=headers, json=body, timeout=timeout)
            elif method.upper() == 'PUT':
                resp = requests.put(url, params=signed_qs, headers=headers, json=body, timeout=timeout)
            elif method.upper() == 'DELETE':
                resp = requests.delete(url, params=signed_qs, headers=headers, json=body, timeout=timeout)
            else:
                raise UserError(_("HTTP method không hỗ trợ: %s") % method)

            data = {}
            if resp.headers.get('Content-Type', '').startswith('application/json'):
                try:
                    data = resp.json()
                except Exception:
                    data = {}

            if resp.status_code != 200 or (data and str(data.get('code')) not in ('0', 0)):
                raise UserError(_("API lỗi: %s") % (resp.text[:500],))
            return data or resp.text
        except Exception as e:
            self._set_error(str(e))
            raise

    def action_refresh_token(self):
        self.ensure_one()
        self._ensure_conf()
        icp = self.env['ir.config_parameter'].sudo()
        refresh_token = self.refresh_token or icp.get_param('tiktok.refresh_token')
        if not refresh_token:
            raise UserError(_("Thiếu refresh_token."))

        url = f"{AUTH_BASE}/api/v2/token/refresh"
        form_data = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            r = requests.post(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=form_data,
                timeout=30,
            )
            if r.status_code == 404:
                r = requests.get(url, params=form_data, timeout=30)
            data = r.json() if r.headers.get('Content-Type','').startswith('application/json') else {}
            if r.status_code != 200 or not data or str(data.get('code')) not in ('0', 0):
                raise UserError(_("Refresh thất bại: %s") % (r.text[:500],))
            d = data.get('data') or {}
            access = d.get('access_token')
            new_refresh = d.get('refresh_token') or refresh_token
            expires_in = d.get('expires_in')  # seconds (older style)
            at_exp_epoch = d.get('access_token_expire_in')  # epoch seconds (newer style)
            rt_exp_epoch = d.get('refresh_token_expire_in')  # epoch seconds (newer style)

            vals = {}
            if access:
                vals['access_token'] = access
                icp.set_param('tiktok.access_token', access)
            if new_refresh:
                vals['refresh_token'] = new_refresh
                icp.set_param('tiktok.refresh_token', new_refresh)

            # Access token expiry: prefer epoch if provided; else fallback to expires_in seconds
            if at_exp_epoch:
                try:
                    vals['token_expiry'] = datetime.utcfromtimestamp(int(at_exp_epoch))
                except Exception:
                    pass
            elif expires_in:
                vals['token_expiry'] = self._utcnow() + timedelta(seconds=int(expires_in))

            # Refresh token expiry if provided
            if rt_exp_epoch:
                try:
                    vals['refresh_token_expiry'] = datetime.utcfromtimestamp(int(rt_exp_epoch))
                except Exception:
                    pass

            # Persist simple hints in ICP (optional)
            if vals.get('token_expiry'):
                icp.set_param('tiktok.access_token_expires_at', vals['token_expiry'].strftime('%Y-%m-%d %H:%M:%S'))
            if vals.get('refresh_token_expiry'):
                icp.set_param('tiktok.refresh_token_expires_at', vals['refresh_token_expiry'].strftime('%Y-%m-%d %H:%M:%S'))

            self.write(vals)
            _logger.info("TikTok refreshed. Access expiry UTC: %s; Refresh expiry UTC: %s", vals.get('token_expiry'), vals.get('refresh_token_expiry'))
            return True
        except Exception as e:
            self._set_error(str(e))
            raise

    def button_get_authorization_code(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f"https://services.tiktokshop.com/open/authorize?app_key={self.app_key}&state=xyz",
            'target': 'new',
        }
    def button_get_access_token(self):
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()
        self.access_token = icp.search([('key', '=', 'tiktok.access_token')], limit=1).value
        refresh = icp.search([('key', '=', 'tiktok.refresh_token')], limit=1).value
        expires_in = icp.search([('key', '=', 'tiktok.access_token_expires_in')], limit=1).value
        vals = {}
        if refresh:
            vals['refresh_token'] = refresh
        if expires_in:
            try:
                vals['token_expiry'] = self._utcnow() + timedelta(seconds=int(expires_in))
            except Exception:
                pass
        if vals:
            self.write(vals)
        return True

