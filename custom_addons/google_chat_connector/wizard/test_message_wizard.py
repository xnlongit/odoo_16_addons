from odoo import models, fields, api

class TestMessageWizard(models.TransientModel):
    _name = 'google.chat.test.wizard'
    _description = 'Test Google Chat Message'

    config_id = fields.Many2one('google.chat.config', required=True)
    space_id = fields.Char('Space ID', required=True)
    message = fields.Text('Message', required=True)

    def action_send_test(self):
        self.config_id.send_message_to_space(self.message, self.space_id)
        # Ghi log lại
        self.env['google.chat.log'].create({
            'config_id': self.config_id.id,
            'message': self.message,
            'space_id': self.space_id,
            'status': 'success',
            'user_id': self.env.user.id,
        })
