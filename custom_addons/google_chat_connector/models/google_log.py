from odoo import models, fields

class GoogleChatLog(models.Model):
    _name = 'google.chat.log'
    _description = 'Google Chat Message Log'
    _order = 'create_date desc'

    config_id = fields.Many2one('google.chat.config', string='Config')
    message = fields.Text('Message')
    space_id = fields.Char('Space ID')
    status = fields.Selection([('success', 'Success'), ('fail', 'Fail')], default='success')
    response = fields.Text('Response')
    create_date = fields.Datetime('Sent At', readonly=True)
    user_id = fields.Many2one('res.users', string='User')
