# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class GchatSpaceCreateWizard(models.TransientModel):
    _name = 'gchat.space.create.wizard'
    _description = 'Create Google Chat Space Wizard'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    space_name = fields.Char('Space Name', required=True)
    space_description = fields.Text('Space Description')
    
    @api.model
    def default_get(self, fields_list):
        """Set default values."""
        res = super().default_get(fields_list)
        if self.env.context.get('default_project_id'):
            project = self.env['project.project'].browse(self.env.context['default_project_id'])
            res['project_id'] = project.id
            res['space_name'] = project.name
        return res

    def action_create_space(self):
        """Create Google Chat space."""
        self.ensure_one()
        
        try:
            # Find configuration
            config = self.env['gchat.config'].search([
                ('company_id', '=', self.project_id.company_id.id),
                ('is_active', '=', True)
            ], limit=1)
            
            if not config:
                raise UserError(_('No active Google Chat configuration found.'))
            
            # Create space record
            space = self.env['gchat.space'].create({
                'project_id': self.project_id.id,
                'config_id': config.id,
                'space_id': f"spaces/{self.project_id.id}_{self.space_name.lower().replace(' ', '_')}",
                'space_display_name': self.space_name,
                'space_type': 'ROOM',
                'active': True
            })
            
            # Create the actual space on Google Chat
            space.action_create_space()
            
            # Enable sync on project
            self.project_id.gchat_sync_enabled = True
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Google Chat space created successfully'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to create Google Chat space: %s') % str(e))


class GchatSpaceLinkWizard(models.TransientModel):
    _name = 'gchat.space.link.wizard'
    _description = 'Link Google Chat Space Wizard'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    space_id = fields.Many2one('gchat.space', string='Existing Space')
    space_name = fields.Char('Space Name')
    space_id_input = fields.Char('Google Chat Space ID', 
                                help='Enter the Google Chat space ID (e.g., spaces/1234567890)')
    
    # New field for available spaces
    available_spaces = fields.Text('Available Spaces', readonly=True, 
                                  help='List of available Google Chat spaces')
    
    @api.model
    def default_get(self, fields_list):
        """Set default values."""
        res = super().default_get(fields_list)
        if self.env.context.get('default_project_id'):
            project = self.env['project.project'].browse(self.env.context['default_project_id'])
            res['project_id'] = project.id
        if self.env.context.get('default_space_id'):
            space = self.env['gchat.space'].browse(self.env.context['default_space_id'])
            res['space_id'] = space.id
            res['space_name'] = space.space_display_name
        
        # Load available spaces
        res['available_spaces'] = self._get_available_spaces()
        return res

    def _get_available_spaces(self):
        """Get list of available Google Chat spaces."""
        try:
            config = self.env['gchat.config'].search([
                ('company_id', '=', self.project_id.company_id.id),
                ('is_active', '=', True)
            ], limit=1)
            
            if not config:
                return "No active Google Chat configuration found."
            
            if not config.access_token:
                return "Please authenticate with Google first (Get OAuth Token)."
            
            spaces = config.list_spaces()
            
            if not spaces:
                return "No spaces found. You may need to create spaces in Google Chat first."
            
            space_list = []
            for space in spaces:
                space_list.append(f"• {space.get('displayName', 'Unknown')} ({space.get('name', 'Unknown')})")
            
            return "Available Spaces:\n" + "\n".join(space_list)
            
        except Exception as e:
            return f"Error loading spaces: {str(e)}"

    def action_refresh_spaces(self):
        """Refresh the list of available spaces."""
        self.ensure_one()
        self.available_spaces = self._get_available_spaces()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Spaces list refreshed'),
                'type': 'success',
            }
        }

    def action_link_space(self):
        """Link project to Google Chat space."""
        self.ensure_one()
        
        try:
            # Find configuration
            config = self.env['gchat.config'].search([
                ('company_id', '=', self.project_id.company_id.id),
                ('is_active', '=', True)
            ], limit=1)
            
            if not config:
                raise UserError(_('No active Google Chat configuration found.'))
            
            # Determine space ID
            space_id_to_link = None
            if self.space_id:
                space_id_to_link = self.space_id.space_id
            elif self.space_id_input:
                space_id_to_link = self.space_id_input
            else:
                raise UserError(_('Please provide a space ID to link.'))
            
            # Check if space is already linked to another project
            existing_space = self.env['gchat.space'].search([
                ('space_id', '=', space_id_to_link),
                ('active', '=', True)
            ], limit=1)
            
            if existing_space and existing_space.project_id != self.project_id:
                raise UserError(_('This Google Chat space is already linked to project: %s') % existing_space.project_id.name)
            
            if existing_space and existing_space.project_id == self.project_id:
                # Already linked
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Info'),
                        'message': _('Project is already linked to this space'),
                        'type': 'info',
                    }
                }
            
            # Create space record
            space = self.env['gchat.space'].create({
                'project_id': self.project_id.id,
                'config_id': config.id,
                'space_id': space_id_to_link,
                'space_display_name': self.space_name or space_id_to_link,
                'active': True
            })
            
            # Enable sync on project
            self.project_id.gchat_sync_enabled = True
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Project linked to Google Chat space successfully'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to link Google Chat space: %s') % str(e))


class GchatMessageWizard(models.TransientModel):
    _name = 'gchat.message.wizard'
    _description = 'Send Google Chat Message Wizard'

    task_id = fields.Many2one('project.task', string='Task', required=True)
    thread_id = fields.Many2one('gchat.thread', string='Thread', required=True)
    message_text = fields.Text('Message', required=True)
    
    @api.model
    def default_get(self, fields_list):
        """Set default values."""
        res = super().default_get(fields_list)
        if self.env.context.get('default_task_id'):
            task = self.env['project.task'].browse(self.env.context['default_task_id'])
            res['task_id'] = task.id
        if self.env.context.get('default_thread_id'):
            thread = self.env['gchat.thread'].browse(self.env.context['default_thread_id'])
            res['thread_id'] = thread.id
        return res

    def action_send_message(self):
        """Send message to Google Chat thread."""
        self.ensure_one()
        
        try:
            # Send message via thread
            response = self.thread_id.push_task_update({'message': self.message_text})
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Message sent to Google Chat successfully'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to send message: %s') % str(e)) 