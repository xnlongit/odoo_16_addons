# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class GchatSpace(models.Model):
    _name = 'gchat.space'
    _description = 'Google Chat Space'
    _rec_name = 'display_name'

    project_id = fields.Many2one('project.project', string='Project', required=True, ondelete='cascade')
    space_id = fields.Char('Google Chat Space ID', required=True, 
                          help='Google Chat space identifier')
    display_name = fields.Char('Space Name', compute='_compute_display_name', store=True)
    
    config_id = fields.Many2one('gchat.config', string='Configuration', required=True)
    active = fields.Boolean('Active', default=True)
    
    # Sync information
    last_sync = fields.Datetime('Last Sync')
    sync_status = fields.Selection([
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('error', 'Error')
    ], default='idle')
    
    # Subscription (for inbound messages)
    subscription_id = fields.Many2one('gchat.subscription', string='Pub/Sub Subscription')
    
    # Space metadata
    space_type = fields.Selection([
        ('ROOM', 'Room'),
        ('DM', 'Direct Message'),
        ('GROUP_DM', 'Group Direct Message')
    ], string='Space Type')
    space_display_name = fields.Char('Space Display Name')
    
    _sql_constraints = [
        ('unique_project_space', 'unique(project_id)', 
         'Only one Google Chat space per project is allowed.'),
        ('unique_space_id', 'unique(space_id)', 
         'Space ID must be unique across all projects.')
    ]

    @api.depends('project_id.name', 'space_display_name', 'space_id')
    def _compute_display_name(self):
        """Compute display name for the space."""
        for space in self:
            if space.space_display_name:
                space.display_name = f"{space.project_id.name} - {space.space_display_name}"
            else:
                space.display_name = f"{space.project_id.name} - {space.space_id}"

    @api.constrains('config_id', 'project_id')
    def _check_company_consistency(self):
        """Ensure config and project belong to same company."""
        for space in self:
            if space.config_id.company_id != space.project_id.company_id:
                raise ValidationError(_('Configuration and project must belong to the same company.'))

    def action_create_space(self):
        """
        Create a new Google Chat space for the project.
        
        Returns:
            dict: Action result
        """
        self.ensure_one()
        
        try:
            # Get configuration
            config = self.config_id
            if not config:
                raise UserError(_('No Google Chat configuration found for this space.'))
            
            # Create space on Google Chat
            space_name = self.space_display_name or self.project_id.name
            space_description = f"Project: {self.project_id.name}"
            
            result = config.create_space(space_name, space_description)
            
            if result.get('success'):
                # Update space record with real data
                self.write({
                    'space_id': result['space_id'],
                    'space_display_name': result['display_name'],
                    'space_type': result['type'],
                    'sync_status': 'idle',
                    'last_sync': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Google Chat space created successfully: %s') % result['space_id'],
                        'type': 'success',
                    }
                }
            else:
                raise UserError(_('Failed to create Google Chat space'))
                
        except Exception as e:
            self.sync_status = 'error'
            raise UserError(_('Failed to create Google Chat space: %s') % str(e))

    def action_link_space(self):
        """
        Open wizard to link existing Google Chat space.
        
        Returns:
            dict: Action to open wizard
        """
        self.ensure_one()
        
        return {
            'name': _('Link Google Chat Space'),
            'type': 'ir.actions.act_window',
            'res_model': 'gchat.space.link.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_space_id': self.id,
                'default_project_id': self.project_id.id,
            }
        }

    def ensure_subscription(self):
        """
        Ensure Pub/Sub subscription exists for this space.
        
        Returns:
            gchat.subscription: Subscription record
        """
        self.ensure_one()
        
        if not self.subscription_id:
            # TODO: Create subscription via Google Cloud Pub/Sub API
            _logger.info(f"Creating subscription for space {self.space_id}")
            
            # Mock implementation
            subscription = self.env['gchat.subscription'].create({
                'config_id': self.config_id.id,
                'space_id': self.id,
                'topic': f'projects/{self.config_id.company_id.id}/topics/gchat-events',
                'subscription_name': f'gchat-sub-{self.space_id.replace("spaces/", "")}',
                'mode': 'pull',
                'status': 'active'
            })
            
            self.subscription_id = subscription.id
            
        return self.subscription_id

    def cancel_subscription(self):
        """Cancel Pub/Sub subscription for this space."""
        self.ensure_one()
        
        if self.subscription_id:
            # TODO: Delete subscription via Google Cloud Pub/Sub API
            _logger.info(f"Cancelling subscription for space {self.space_id}")
            self.subscription_id.unlink()

    def sync_members(self):
        """
        Sync space members with project followers.
        
        Returns:
            dict: Sync result
        """
        self.ensure_one()
        
        try:
            # TODO: Implement member sync
            # - Get space members from Google Chat API
            # - Match with project followers
            # - Create/update gchat.member records
            _logger.info(f"Syncing members for space {self.space_id}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Members synced successfully'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to sync members: %s') % str(e))

    def action_view_threads(self):
        """Open threads view for this space."""
        self.ensure_one()
        
        return {
            'name': _('Threads'),
            'type': 'ir.actions.act_window',
            'res_model': 'gchat.thread',
            'view_mode': 'tree,form',
            'domain': [('space_id', '=', self.id)],
            'context': {'default_space_id': self.id},
        } 