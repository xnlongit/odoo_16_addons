from odoo import models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def create(self, vals):
        order = super().create(vals)
        self.env['google.chat.config'].send_notification('sale.order', 'create', order)
        return order

    def write(self, vals):
        res = super().write(vals)
        for order in self:
            self.env['google.chat.config'].send_notification('sale.order', 'write', order)
        return res
