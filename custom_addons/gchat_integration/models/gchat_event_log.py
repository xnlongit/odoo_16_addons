# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class GchatEventLog(models.Model):
    _name = 'gchat.event.log'
    _description = 'Google Chat Event Log'
    _rec_name = 'external_event_id'
    _order = 'create_date desc'

    external_event_id = fields.Char('External Event ID', required=True, 
                                   help='Unique identifier from Google Chat')
    source = fields.Selection([
        ('chat', 'Google Chat'),
        ('tasks', 'Google Tasks')
    ], string='Source', required=True, default='chat')
    
    event_type = fields.Char('Event Type', required=True,
                            help='Type of event (e.g., MESSAGE_CREATED, MEMBER_ADDED)')
    
    # Related records
    space_id = fields.Many2one('gchat.space', string='Space', ondelete='cascade')
    thread_key = fields.Char('Thread Key', help='Thread identifier for threaded messages')
    
    # Event data
    payload_json = fields.Text('Event Payload (JSON)', help='Full event payload from Google')
    
    # Processing status
    status = fields.Selection([
        ('new', 'New'),
        ('processing', 'Processing'),
        ('done', 'Processed'),
        ('error', 'Error'),
        ('skipped', 'Skipped')
    ], string='Status', default='new')
    
    processed_at = fields.Datetime('Processed At')
    error = fields.Text('Error Message')
    
    # Additional metadata
    user_email = fields.Char('User Email', help='Email of user who triggered the event')
    message_text = fields.Text('Message Text', help='Extracted message text if applicable')
    
    # Timestamps
    create_date = fields.Datetime('Created At', readonly=True)
    write_date = fields.Datetime('Updated At', readonly=True)
    
    _sql_constraints = [
        ('unique_external_event_id', 'unique(external_event_id)', 
         'External event ID must be unique.'),
    ]

    def process_incoming(self, envelope, event_json):
        """
        Process incoming event from Google Chat.
        
        Args:
            envelope (dict): Pub/Sub envelope with message_id, publish_time, etc.
            event_json (dict): Decoded event data from Google Chat
            
        Returns:
            bool: True if processed successfully
        """
        self.ensure_one()
        
        try:
            # Check for duplicate processing
            if self.status in ['done', 'processing']:
                _logger.info(f"Event {self.external_event_id} already processed, skipping")
                return True
            
            # Mark as processing
            self.write({'status': 'processing'})
            
            # Extract basic event info
            event_type = event_json.get('eventType', 'UNKNOWN')
            space_name = event_json.get('space', {}).get('name', '')
            thread_name = event_json.get('thread', {}).get('name', '')
            user_email = event_json.get('user', {}).get('email', '')
            
            # Update event with extracted info
            self.write({
                'event_type': event_type,
                'user_email': user_email,
                'message_text': self._extract_message_text(event_json)
            })
            
            # Find related space and thread
            space = self._find_space(space_name)
            thread = self._find_thread(space, thread_name) if space else None
            
            if space:
                self.space_id = space.id
            if thread:
                self.thread_key = thread.thread_key
            
            # Route event based on type
            if event_type == 'MESSAGE_CREATED':
                self._process_message_created(event_json)
            elif event_type == 'MESSAGE_UPDATED':
                self._process_message_updated(event_json)
            elif event_type == 'MEMBER_ADDED':
                self._process_member_added(event_json)
            elif event_type == 'MEMBER_REMOVED':
                self._process_member_removed(event_json)
            else:
                _logger.info(f"Unhandled event type: {event_type}")
                self.write({'status': 'skipped'})
                return True
            
            # Mark as processed
            self.write({
                'status': 'done',
                'processed_at': datetime.now()
            })
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Failed to process event {self.external_event_id}: {error_msg}")
            
            self.write({
                'status': 'error',
                'error': error_msg,
                'processed_at': datetime.now()
            })
            
            return False

    def _find_space(self, space_name):
        """Find space record by Google Chat space name."""
        if not space_name:
            return False
            
        return self.env['gchat.space'].search([
            ('space_id', '=', space_name),
            ('active', '=', True)
        ], limit=1)

    def _find_thread(self, space, thread_name):
        """Find thread record by Google Chat thread name."""
        if not space or not thread_name:
            return False
            
        # Extract thread key from full name
        thread_key = thread_name.split('/')[-1] if '/' in thread_name else thread_name
        
        return self.env['gchat.thread'].search([
            ('space_id', '=', space.id),
            ('thread_key', '=', thread_key),
            ('active', '=', True)
        ], limit=1)

    def _extract_message_text(self, event_json):
        """Extract message text from event JSON."""
        message = event_json.get('message', {})
        if message.get('text'):
            return message['text']
        elif message.get('cards'):
            for card in message['cards']:
                if card.get('header', {}).get('title'):
                    return card['header']['title']
        return ''

    def _process_message_created(self, event_json):
        """Process MESSAGE_CREATED event."""
        if not self.thread_key:
            return
        
        thread = self.env['gchat.thread'].search([
            ('thread_key', '=', self.thread_key),
            ('active', '=', True)
        ], limit=1)
        
        if not thread:
            return
        
        task = thread.task_id
        
        # Create mail.message in task chatter
        if self.message_text and self.user_email:
            user = self.env['res.users'].search([
                ('email', '=', self.user_email)
            ], limit=1)
            
            self.env['mail.message'].create({
                'model': 'project.task',
                'res_id': task.id,
                'message_type': 'comment',
                'subtype_id': self.env.ref('mail.mt_comment').id,
                'body': f"<p><strong>Google Chat message from {self.user_email}:</strong></p><p>{self.message_text}</p>",
                'author_id': user.partner_id.id if user else False,
                'email_from': self.user_email,
            })

    def _process_message_updated(self, event_json):
        """Process MESSAGE_UPDATED event."""
        self._process_message_created(event_json)

    def _process_member_added(self, event_json):
        """Process MEMBER_ADDED event."""
        if not self.space_id:
            return
        
        member_info = event_json.get('member', {})
        email = member_info.get('email', '')
        
        if email:
            member = self.env['gchat.member'].search([
                ('space_id', '=', self.space_id.id),
                ('email', '=', email)
            ], limit=1)
            
            if not member:
                self.env['gchat.member'].create({
                    'space_id': self.space_id.id,
                    'email': email,
                    'google_user_id': member_info.get('name', '').split('/')[-1],
                    'role': member_info.get('role', 'MEMBER'),
                    'state': 'active'
                })
            else:
                member.write({
                    'role': member_info.get('role', 'MEMBER'),
                    'state': 'active',
                    'last_sync': datetime.now()
                })

    def _process_member_removed(self, event_json):
        """Process MEMBER_REMOVED event."""
        if not self.space_id:
            return
        
        member_info = event_json.get('member', {})
        email = member_info.get('email', '')
        
        if email:
            member = self.env['gchat.member'].search([
                ('space_id', '=', self.space_id.id),
                ('email', '=', email)
            ], limit=1)
            
            if member:
                member.write({
                    'state': 'removed',
                    'last_sync': datetime.now()
                })

    def action_retry_processing(self):
        """Retry processing failed event."""
        self.ensure_one()
        
        if self.status == 'error':
            self.write({'status': 'new'})
            envelope = {'message_id': self.external_event_id}
            event_json = json.loads(self.payload_json) if self.payload_json else {}
            return self.process_incoming(envelope, event_json)
        
        return False 