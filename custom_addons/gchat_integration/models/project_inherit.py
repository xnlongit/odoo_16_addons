# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    gchat_space_id = fields.Many2one('gchat.space', string='Google Chat Space', 
                                    compute='_compute_gchat_space', store=True)
    gchat_sync_enabled = fields.Boolean('Google Chat Sync Enabled', default=False)
    
    # Computed fields for UI
    has_gchat_space = fields.Boolean('Has Google Chat Space', compute='_compute_has_gchat_space')
    gchat_space_name = fields.Char('Space Name', compute='_compute_gchat_space_name')

    @api.depends('gchat_sync_enabled')
    def _compute_gchat_space(self):
        """Compute the associated Google Chat space."""
        for project in self:
            if project.gchat_sync_enabled:
                space = self.env['gchat.space'].search([
                    ('project_id', '=', project.id),
                    ('active', '=', True)
                ], limit=1)
                project.gchat_space_id = space
            else:
                project.gchat_space_id = False

    @api.depends('gchat_space_id')
    def _compute_has_gchat_space(self):
        """Compute if project has a Google Chat space."""
        for project in self:
            project.has_gchat_space = bool(project.gchat_space_id)

    @api.depends('gchat_space_id.space_display_name', 'gchat_space_id.space_id')
    def _compute_gchat_space_name(self):
        """Compute the display name of the Google Chat space."""
        for project in self:
            if project.gchat_space_id:
                project.gchat_space_name = project.gchat_space_id.space_display_name or project.gchat_space_id.space_id
            else:
                project.gchat_space_name = ''

    def action_sync_with_gchat(self):
        """
        Open wizard to sync project with Google Chat.
        
        Returns:
            dict: Action to open wizard
        """
        self.ensure_one()
        
        # Check if configuration exists
        config = self.env['gchat.config'].search([
            ('company_id', '=', self.company_id.id),
            ('is_active', '=', True)
        ], limit=1)
        
        if not config:
            raise UserError(_('No active Google Chat configuration found for your company. Please configure Google Chat integration first.'))
        
        # Check if space already exists
        existing_space = self.env['gchat.space'].search([
            ('project_id', '=', self.id),
            ('active', '=', True)
        ], limit=1)
        
        if existing_space:
            # Open link wizard to modify existing space
            return {
                'name': _('Link Google Chat Space'),
                'type': 'ir.actions.act_window',
                'res_model': 'gchat.space.link.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_project_id': self.id,
                    'default_space_id': existing_space.id,
                    'default_space_name': existing_space.space_display_name,
                }
            }
        else:
            # Open create wizard
            return {
                'name': _('Create Google Chat Space'),
                'type': 'ir.actions.act_window',
                'res_model': 'gchat.space.create.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_project_id': self.id,
                }
            }

    def action_create_gchat_space(self):
        """
        Create a new Google Chat space for this project.
        
        Returns:
            dict: Action result
        """
        self.ensure_one()
        
        try:
            # Find configuration
            config = self.env['gchat.config'].search([
                ('company_id', '=', self.company_id.id),
                ('is_active', '=', True)
            ], limit=1)
            
            if not config:
                raise UserError(_('No active Google Chat configuration found.'))
            
            # Create space record
            space = self.env['gchat.space'].create({
                'project_id': self.id,
                'config_id': config.id,
                'space_id': f"spaces/{self.id}_{self.name.lower().replace(' ', '_')}",
                'space_display_name': self.name,
                'space_type': 'ROOM',
                'active': True
            })
            
            # Create the actual space on Google Chat
            space.action_create_space()
            
            # Enable sync
            self.gchat_sync_enabled = True
            
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

    def action_link_gchat_space(self, space_id):
        """
        Link project to existing Google Chat space.
        
        Args:
            space_id (str): Google Chat space ID
            
        Returns:
            dict: Action result
        """
        self.ensure_one()
        
        try:
            # Find configuration
            config = self.env['gchat.config'].search([
                ('company_id', '=', self.company_id.id),
                ('is_active', '=', True)
            ], limit=1)
            
            if not config:
                raise UserError(_('No active Google Chat configuration found.'))
            
            # Check if space is already linked to another project
            existing_space = self.env['gchat.space'].search([
                ('space_id', '=', space_id),
                ('active', '=', True)
            ], limit=1)
            
            if existing_space and existing_space.project_id != self:
                raise UserError(_('This Google Chat space is already linked to project: %s') % existing_space.project_id.name)
            
            if existing_space and existing_space.project_id == self:
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
                'project_id': self.id,
                'config_id': config.id,
                'space_id': space_id,
                'active': True
            })
            
            # Enable sync
            self.gchat_sync_enabled = True
            
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

    def action_view_gchat_space(self):
        """Open Google Chat space view."""
        self.ensure_one()
        
        if not self.gchat_space_id:
            raise UserError(_('No Google Chat space linked to this project.'))
        
        return {
            'name': _('Google Chat Space'),
            'type': 'ir.actions.act_window',
            'res_model': 'gchat.space',
            'res_id': self.gchat_space_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_gchat_threads(self):
        """Open Google Chat threads view for this project."""
        self.ensure_one()
        
        if not self.gchat_space_id:
            raise UserError(_('No Google Chat space linked to this project.'))
        
        return {
            'name': _('Google Chat Threads'),
            'type': 'ir.actions.act_window',
            'res_model': 'gchat.thread',
            'view_mode': 'tree,form',
            'domain': [('space_id', '=', self.gchat_space_id.id)],
            'context': {'default_space_id': self.gchat_space_id.id},
        } 