from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    ward_id = fields.Many2one('res.country.ward', string='Ward',
                              domain="[('state_id','=', state_id)]")
