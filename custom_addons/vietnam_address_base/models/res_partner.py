# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api


class Partner(models.Model):
    _inherit = 'res.partner'

    ward_id = fields.Many2one(comodel_name='res.country.ward', string='Ward',
                              domain="[('state_id', '=', state_id)]")

    shipping_address = fields.Char(compute='_compute_complete_shipping_address')

    @staticmethod
    def replace_address_name(pattern, name):
        return name.replace(pattern, '').strip()

    @staticmethod
    def replace_province_text(name):
        return name.replace('Tỉnh ', '').replace('Thành phố ', '').strip()

    @api.depends('street', 'ward_id', 'state_id')
    def _compute_complete_shipping_address(self):
        for record in self:
            address_parts = []
            
            if record.street:
                address_parts.append(record.street)
            
            if record.ward_id:
                address_parts.append(record.ward_id.name)
            
            if record.state_id:
                address_parts.append(record.state_id.name)
            
            if record.country_id:
                address_parts.append(record.country_id.name)
            
            record.shipping_address = ', '.join(address_parts) if address_parts else ''
