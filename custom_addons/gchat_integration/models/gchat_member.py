# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class GchatMember(models.Model):
    _name = 'gchat.member'
    _description = 'Google Chat Space Member'
    _rec_name = 'display_name'

    space_id = fields.Many2one('gchat.space', string='Space', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='cascade')
    
    # Google Chat user info
    email = fields.Char('Email', required=True)
    google_user_id = fields.Char('Google User ID')
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    
    # Member details
    role = fields.Selection([
        ('ROLE_UNSPECIFIED', 'Unspecified'),
        ('OWNER', 'Owner'),
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Member')
    ], string='Role', default='MEMBER')
    
    state = fields.Selection([
        ('active', 'Active'),
        ('invited', 'Invited'),
        ('pending', 'Pending'),
        ('removed', 'Removed')
    ], string='State', default='active')
    
    # Sync information
    last_sync = fields.Datetime('Last Sync')
    sync_status = fields.Selection([
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('error', 'Error')
    ], default='idle')
    
    # Additional info
    avatar_url = fields.Char('Avatar URL')
    is_bot = fields.Boolean('Is Bot', default=False)
    
    _sql_constraints = [
        ('unique_space_email', 'unique(space_id, email)', 
         'Email must be unique per space.'),
    ]

    @api.depends('partner_id.name', 'email', 'google_user_id')
    def _compute_display_name(self):
        """Compute display name for the member."""
        for member in self:
            if member.partner_id:
                member.display_name = f"{member.partner_id.name} ({member.email})"
            elif member.google_user_id:
                member.display_name = f"{member.google_user_id} ({member.email})"
            else:
                member.display_name = member.email

    @api.constrains('space_id', 'partner_id')
    def _check_company_consistency(self):
        """Ensure space and partner belong to same company."""
        for member in self:
            if member.partner_id and member.space_id.project_id.company_id != member.partner_id.company_id:
                raise ValidationError(_('Space and partner must belong to the same company.'))

    def invite(self):
        """
        Invite member to Google Chat space.
        
        Returns:
            bool: True if successful
        """
        self.ensure_one()
        
        try:
            # TODO: Implement Google Chat API call to invite member
            # - Use space.config_id.get_client() to get authenticated client
            # - Call Chat API to invite user to space
            _logger.info(f"Inviting {self.email} to space {self.space_id.space_id}")
            
            # Mock implementation
            self.write({
                'state': 'invited',
                'last_sync': fields.Datetime.now()
            })
            
            return True
            
        except Exception as e:
            self.write({
                'state': 'error',
                'sync_status': 'error'
            })
            _logger.error(f"Failed to invite member: {str(e)}")
            return False

    def remove(self):
        """
        Remove member from Google Chat space.
        
        Returns:
            bool: True if successful
        """
        self.ensure_one()
        
        try:
            # TODO: Implement Google Chat API call to remove member
            # - Use space.config_id.get_client() to get authenticated client
            # - Call Chat API to remove user from space
            _logger.info(f"Removing {self.email} from space {self.space_id.space_id}")
            
            # Mock implementation
            self.write({
                'state': 'removed',
                'last_sync': fields.Datetime.now()
            })
            
            return True
            
        except Exception as e:
            _logger.error(f"Failed to remove member: {str(e)}")
            return False

    def resolve_partner(self):
        """
        Try to find and link Odoo partner based on email.
        
        Returns:
            res.partner: Found partner or False
        """
        self.ensure_one()
        
        if not self.email:
            return False
            
        # Try to find partner by email
        partner = self.env['res.partner'].search([
            ('email', '=', self.email)
        ], limit=1)
        
        if partner:
            self.partner_id = partner.id
            return partner
            
        return False

    def action_invite(self):
        """Action to invite member."""
        self.ensure_one()
        
        if self.invite():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Member invited successfully'),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_('Failed to invite member'))

    def action_remove(self):
        """Action to remove member."""
        self.ensure_one()
        
        if self.remove():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Member removed successfully'),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_('Failed to remove member'))

    def action_resolve_partner(self):
        """Action to resolve partner."""
        self.ensure_one()
        
        partner = self.resolve_partner()
        if partner:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Partner linked: %s') % partner.name,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Info'),
                    'message': _('No partner found with email: %s') % self.email,
                    'type': 'info',
                }
            }

    @api.model
    def sync_space_members(self, space):
        """
        Sync members from Google Chat space.
        
        Args:
            space: gchat.space record
            
        Returns:
            dict: Sync result
        """
        try:
            # TODO: Implement member sync from Google Chat API
            # - Get space members from Chat API
            # - Create/update gchat.member records
            # - Link with existing partners
            _logger.info(f"Syncing members for space {space.space_id}")
            
            # Mock implementation
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