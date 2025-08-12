from odoo import models, fields

class GoogleChatMapping(models.Model):
    _name = 'google.chat.mapping'
    _description = 'Google Chat Notification Mapping'

    model_id = fields.Many2one(
        'ir.model',
        string='Odoo Model',
        required=True,
        ondelete='cascade'
    )
    event_type = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update'),
        ('unlink', 'Delete'),
        # ... các event khác
    ], required=True)
    space_id = fields.Char('Google Chat Space ID', required=True)
    active = fields.Boolean(default=True)
    template_id = fields.Many2one('mail.template', string='Message Template')
