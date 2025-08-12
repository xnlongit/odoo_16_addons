# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class GchatSubscription(models.Model):
    _name = 'gchat.subscription'
    _description = 'Google Chat Pub/Sub Subscription'
    _rec_name = 'subscription_name'

    config_id = fields.Many2one('gchat.config', string='Configuration', required=True)
    space_id = fields.Many2one('gchat.space', string='Space', ondelete='cascade')
    
    # Pub/Sub details
    topic = fields.Char('Topic', required=True, 
                       help='Google Cloud Pub/Sub topic name')
    subscription_name = fields.Char('Subscription Name', required=True,
                                   help='Google Cloud Pub/Sub subscription name')
    
    # Configuration
    mode = fields.Selection([
        ('pull', 'Pull'),
        ('push', 'Push')
    ], string='Mode', required=True, default='pull')
    
    # Status
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('error', 'Error'),
        ('creating', 'Creating'),
        ('deleting', 'Deleting')
    ], string='Status', default='creating')
    
    # Expiry information
    expires_at = fields.Datetime('Expires At')
    last_message_id = fields.Char('Last Message ID')
    last_message_time = fields.Datetime('Last Message Time')
    
    # Error tracking
    error_message = fields.Text('Last Error')
    retry_count = fields.Integer('Retry Count', default=0)
    
    # Push configuration (if mode is push)
    push_endpoint = fields.Char('Push Endpoint URL')
    push_attributes = fields.Text('Push Attributes (JSON)')
    
    _sql_constraints = [
        ('unique_subscription_name', 'unique(subscription_name)', 
         'Subscription name must be unique.'),
    ]

    @api.constrains('config_id', 'space_id')
    def _check_company_consistency(self):
        """Ensure config and space belong to same company."""
        for subscription in self:
            if subscription.space_id and subscription.config_id.company_id != subscription.space_id.project_id.company_id:
                raise ValidationError(_('Configuration and space must belong to the same company.'))

    def create_on_gcp(self):
        """
        Create subscription on Google Cloud Pub/Sub.
        
        Returns:
            bool: True if successful
        """
        self.ensure_one()
        
        try:
            # TODO: Implement Google Cloud Pub/Sub API call
            # - Use config.get_client() to get authenticated client
            # - Call Pub/Sub API to create subscription
            # - Set push endpoint if mode is push
            _logger.info(f"Creating subscription {self.subscription_name} on GCP")
            
            # Mock implementation
            self.write({
                'status': 'active',
                'expires_at': datetime.now() + timedelta(days=7),  # 7 days expiry
                'error_message': False
            })
            
            return True
            
        except Exception as e:
            self.write({
                'status': 'error',
                'error_message': str(e)
            })
            _logger.error(f"Failed to create subscription: {str(e)}")
            return False

    def renew_on_gcp(self):
        """
        Renew subscription on Google Cloud Pub/Sub.
        
        Returns:
            bool: True if successful
        """
        self.ensure_one()
        
        try:
            # TODO: Implement subscription renewal
            # - Extend subscription expiry
            # - Update push endpoint if needed
            _logger.info(f"Renewing subscription {self.subscription_name}")
            
            # Mock implementation
            self.write({
                'expires_at': datetime.now() + timedelta(days=7),
                'status': 'active',
                'error_message': False
            })
            
            return True
            
        except Exception as e:
            self.write({
                'status': 'error',
                'error_message': str(e)
            })
            _logger.error(f"Failed to renew subscription: {str(e)}")
            return False

    def delete_on_gcp(self):
        """
        Delete subscription on Google Cloud Pub/Sub.
        
        Returns:
            bool: True if successful
        """
        self.ensure_one()
        
        try:
            # TODO: Implement subscription deletion
            # - Call Pub/Sub API to delete subscription
            _logger.info(f"Deleting subscription {self.subscription_name} from GCP")
            
            # Mock implementation
            self.write({'status': 'deleting'})
            
            return True
            
        except Exception as e:
            self.write({
                'status': 'error',
                'error_message': str(e)
            })
            _logger.error(f"Failed to delete subscription: {str(e)}")
            return False

    def is_expiring(self, days_threshold=1):
        """
        Check if subscription is expiring soon.
        
        Args:
            days_threshold (int): Days before expiry to consider as expiring
            
        Returns:
            bool: True if expiring soon
        """
        if not self.expires_at:
            return False
            
        threshold_date = datetime.now() + timedelta(days=days_threshold)
        return self.expires_at <= threshold_date

    def action_create(self):
        """Action to create subscription on GCP."""
        self.ensure_one()
        
        if self.create_on_gcp():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Subscription created successfully'),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_('Failed to create subscription'))

    def action_renew(self):
        """Action to renew subscription."""
        self.ensure_one()
        
        if self.renew_on_gcp():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Subscription renewed successfully'),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_('Failed to renew subscription'))

    def action_delete(self):
        """Action to delete subscription."""
        self.ensure_one()
        
        if self.delete_on_gcp():
            self.unlink()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Subscription deleted successfully'),
                    'type': 'success',
                }
            }
        else:
            raise UserError(_('Failed to delete subscription'))

    @api.model
    def _cron_check_expiring_subscriptions(self):
        """
        Cron job to check for expiring subscriptions.
        """
        expiring_subs = self.search([
            ('status', '=', 'active'),
            ('expires_at', '<=', datetime.now() + timedelta(days=1))
        ])
        
        for subscription in expiring_subs:
            _logger.warning(f"Subscription {subscription.subscription_name} is expiring soon")
            # TODO: Send notification to admin or auto-renew

    @api.model
    def _cron_cleanup_expired_subscriptions(self):
        """
        Cron job to cleanup expired subscriptions.
        """
        expired_subs = self.search([
            ('status', '=', 'expired'),
            ('expires_at', '<', datetime.now() - timedelta(days=7))
        ])
        
        for subscription in expired_subs:
            _logger.info(f"Cleaning up expired subscription {subscription.subscription_name}")
            subscription.unlink() 