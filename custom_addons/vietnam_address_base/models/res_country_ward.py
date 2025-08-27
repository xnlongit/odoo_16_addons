from odoo import models, fields, api


class Ward(models.Model):
    _name = 'res.country.ward'
    _description = 'ward'
    _order = 'name'

    code = fields.Char(string='Ward Code')
    name = fields.Char(string='Ward name')
    slug = fields.Char(string='Ward 3L')
    slug2 = fields.Char(string='Ward 2L')
    state_id = fields.Many2one('res.country.state', 'State',
                               domain="[('country_id', '=', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', required=True)
    type = fields.Selection(selection=[
        ('0', 'Phường'),
        ('1', 'Xã'),
        ('2', 'Khác')
    ], string='Type')
