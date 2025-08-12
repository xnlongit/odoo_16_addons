from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    space_id = fields.Char('Space ID')
