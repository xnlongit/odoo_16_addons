# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from urllib.parse import urlparse, parse_qs
import json

class TiktokApiTesterWizard(models.TransientModel):
    _name = 'tiktok.api.tester.wizard'
    _description = 'TikTok API Tester'

    preset = fields.Selection([
        ('none', 'Custom'),
        ('get_order_list_202309', 'Get Order List (202309)'),
    ], string='Preset', default='none')

    config_id = fields.Many2one('tiktok.shop.config', string='Connection', required=True)
    url = fields.Char('API URL', required=True, help='Full path or absolute URL, e.g. /order/202309/orders or https://open-api.tiktokglobalshop.com/order/202309/orders')
    method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
    ], string='Method', default='GET', required=True)
    query_json = fields.Text('Query (JSON)', help='Optional query parameters as JSON object')
    body_json = fields.Text('Body (JSON)', help='Optional request body as JSON object')
    content_type = fields.Selection([
        ('application/json', 'application/json'),
        ('multipart/form-data', 'multipart/form-data'),
    ], string='Content-Type', default='application/json', required=True)
    response_text = fields.Text('Response', readonly=True)

    @api.onchange('preset')
    def _onchange_preset(self):
        if self.preset == 'get_order_list_202309':
            self.method = 'GET'
            self.url = '/order/202309/orders'
            template = {
                "shop_cipher": "",
                "page_size": 20,
                # Optional filters (at least one filter like ids or a time window is typically needed):
                # "ids": "123,456",
                # "update_time_ge": 0,
                # "update_time_le": 0,
                # "create_time_ge": 0,
                # "create_time_le": 0,
                # "order_status": "",
            }
            self.query_json = json.dumps(template, ensure_ascii=False)
            self.body_json = False
        else:
            pass

    @api.onchange('url')
    def _onchange_url(self):
        if self.url:
            try:
                parsed = urlparse(self.url)
                query_map = {k: v[0] if isinstance(v, list) and v else v for k, v in parse_qs(parsed.query).items()}
                if query_map:
                    self.query_json = json.dumps(query_map)
            except Exception:
                pass

    def _parse_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            path = parsed.path or '/'
            query_map = {k: v[0] if isinstance(v, list) and v else v for k, v in parse_qs(parsed.query).items()}
        else:
            path = url if url.startswith('/') else f'/{url}'
            query_map = {}
        return path, query_map

    def _validate_get_order_list_query(self, merged_query):
        # Per doc, common required: app_key/timestamp/sign handled by code; endpoint requires shop identification and typically a filter.
        if not merged_query.get('shop_cipher') and not merged_query.get('shop_id'):
            raise UserError(_("Thiếu 'shop_cipher' hoặc 'shop_id' cho Get Order List."))
        has_ids = bool(merged_query.get('ids'))
        has_update_window = merged_query.get('update_time_ge') and merged_query.get('update_time_le')
        has_create_window = merged_query.get('create_time_ge') and merged_query.get('create_time_le')
        # If none provided, guide the user. Some regions require at least one filter to avoid massive scans.
        if not (has_ids or has_update_window or has_create_window):
            raise UserError(_("Thiếu filter. Thêm 'ids' (chuỗi cách nhau bằng dấu phẩy) hoặc cặp thời gian 'update_time_ge/update_time_le' hoặc 'create_time_ge/create_time_le'."))
        # Default page_size if missing
        if not merged_query.get('page_size'):
            merged_query['page_size'] = 20
        return merged_query

    def action_execute(self):
        self.ensure_one()
        config = self.config_id
        if not config:
            raise UserError(_('Please choose a TikTok connection.'))
        if not self.url:
            raise UserError(_('Please input API URL.'))

        path, query_from_url = self._parse_url(self.url)

        merged_query = dict(query_from_url)
        if self.query_json:
            try:
                obj = json.loads(self.query_json)
                if not isinstance(obj, dict):
                    raise ValueError('query_json must be an object')
                merged_query.update(obj)
            except Exception as e:
                raise UserError(_('Invalid Query JSON: %s') % e)

        body = {}
        if self.body_json:
            try:
                body = json.loads(self.body_json)
                if not isinstance(body, dict):
                    raise ValueError('body_json must be an object')
            except Exception as e:
                raise UserError(_('Invalid Body JSON: %s') % e)

        # Preset-specific validations
        if self.preset == 'get_order_list_202309':
            merged_query = self._validate_get_order_list_query(merged_query)

        try:
            result = config.api_request(
                method=self.method,
                path=path,
                query=merged_query,
                body=body,
                with_token=True,
                content_type=self.content_type,
            )
            if isinstance(result, (dict, list)):
                self.response_text = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                self.response_text = str(result)
        except Exception as e:
            self.response_text = str(e)
            raise

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tiktok.api.tester.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        } 