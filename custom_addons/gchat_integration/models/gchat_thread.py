# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class GchatThread(models.Model):
    _name = 'gchat.thread'
    _description = 'Google Chat Thread'
    _rec_name = 'display_name'

    task_id = fields.Many2one('project.task', string='Task', required=True, ondelete='cascade')
    space_id = fields.Many2one('gchat.space', string='Space', required=True, ondelete='cascade')
    
    thread_key = fields.Char('Thread Key', required=True, 
                            help='Google Chat thread identifier')
    display_name = fields.Char('Thread Name', compute='_compute_display_name', store=True)
    
    active = fields.Boolean('Active', default=True)
    
    # Sync information
    last_event_ts = fields.Datetime('Last Event Timestamp')
    last_message_id = fields.Char('Last Message ID')
    
    # Thread metadata
    thread_name = fields.Char('Thread Name')
    thread_type = fields.Selection([
        ('THREAD_TYPE_UNSPECIFIED', 'Unspecified'),
        ('THREAD', 'Thread'),
        ('SPACE', 'Space')
    ], string='Thread Type', default='THREAD')
    
    # Message count
    message_count = fields.Integer('Message Count', default=0)
    
    _sql_constraints = [
        ('unique_task_thread', 'unique(task_id)', 
         'Only one Google Chat thread per task is allowed.'),
        ('unique_thread_key', 'unique(thread_key)', 
         'Thread key must be unique across all spaces.')
    ]

    @api.depends('task_id.name', 'thread_name', 'thread_key')
    def _compute_display_name(self):
        """Compute display name for the thread."""
        for thread in self:
            if thread.thread_name:
                thread.display_name = f"{thread.task_id.name} - {thread.thread_name}"
            else:
                thread.display_name = f"{thread.task_id.name} - {thread.thread_key}"

    @api.constrains('space_id', 'task_id')
    def _check_project_consistency(self):
        """Ensure space and task belong to same project."""
        for thread in self:
            if thread.space_id.project_id != thread.task_id.project_id:
                raise ValidationError(_('Space and task must belong to the same project.'))

    def ensure_thread(self):
        """
        Ensure thread exists in Google Chat.
        Creates thread if it doesn't exist.
        
        Returns:
            bool: True if thread exists or was created successfully
        """
        self.ensure_one()
        
        if not self.thread_key:
            # Generate thread key based on task ID
            self.thread_key = str(self.task_id.id)
            
        try:
            # TODO: Implement Google Chat API call to ensure thread exists
            # - Use space.config_id.get_client() to get authenticated client
            # - Call Chat API to create/verify thread
            # - Update thread metadata
            _logger.info(f"Ensuring thread exists for task {self.task_id.name}")
            
            # Mock implementation - thread is created when first message is sent
            return True
            
        except Exception as e:
            _logger.error(f"Failed to ensure thread: {str(e)}")
            return False

    def push_task_update(self, vals_changed):
        """
        Push task update to Google Chat thread.
        
        Args:
            vals_changed (dict): Changed field values
            
        Returns:
            dict: API response
        """
        self.ensure_one()
        
        if not self.ensure_thread():
            raise UserError(_('Failed to ensure thread exists'))
            
        try:
            # Format message based on changes
            message_text = self._format_task_update_message(vals_changed)
            
            # Send message via config
            config = self.space_id.config_id
            response = config.send_chat(
                space_id=self.space_id.space_id,
                text=message_text,
                thread_key=self.thread_key
            )
            
            # Update last message info
            if response.get('success'):
                self.last_message_id = response.get('message_id')
                self.message_count += 1
                
            return response
            
        except Exception as e:
            _logger.error(f"Failed to push task update: {str(e)}")
            raise UserError(_('Failed to send message to Google Chat: %s') % str(e))

    def push_attachment(self, attachment):
        """
        Push attachment to Google Chat thread.
        
        Args:
            attachment: Mail attachment record
            
        Returns:
            dict: API response
        """
        self.ensure_one()
        
        if not self.ensure_thread():
            raise UserError(_('Failed to ensure thread exists'))
            
        try:
            # TODO: Implement attachment upload
            # - Upload file to Google Drive or similar
            # - Create message with attachment card
            _logger.info(f"Pushing attachment {attachment.name} to thread {self.thread_key}")
            
            # Mock implementation
            return {'success': True, 'message_id': 'mock_attachment_123'}
            
        except Exception as e:
            _logger.error(f"Failed to push attachment: {str(e)}")
            raise UserError(_('Failed to send attachment to Google Chat: %s') % str(e))

    def _format_task_update_message(self, vals_changed):
        """
        Format task update message for Google Chat.
        
        Args:
            vals_changed (dict): Changed field values
            
        Returns:
            str: Formatted message text
        """
        task = self.task_id
        changes = []
        
        # Map field changes to readable messages
        field_mapping = {
            'name': 'Name',
            'user_id': 'Assignee',
            'stage_id': 'Stage',
            'priority': 'Priority',
            'date_deadline': 'Deadline',
            'description': 'Description',
            'tag_ids': 'Tags'
        }
        
        for field, value in vals_changed.items():
            if field in field_mapping:
                if field == 'user_id':
                    user = self.env['res.users'].browse(value)
                    changes.append(f"*{field_mapping[field]}*: {user.name}")
                elif field == 'stage_id':
                    stage = self.env['project.task.type'].browse(value)
                    changes.append(f"*{field_mapping[field]}*: {stage.name}")
                elif field == 'priority':
                    priority_labels = {'0': 'Low', '1': 'Normal', '2': 'High'}
                    changes.append(f"*{field_mapping[field]}*: {priority_labels.get(str(value), value)}")
                elif field == 'date_deadline':
                    changes.append(f"*{field_mapping[field]}*: {value}")
                else:
                    changes.append(f"*{field_mapping[field]}*: {value}")
        
        if changes:
            message = f"📋 *Task Updated: {task.name}*\n\n"
            message += "\n".join(changes)
            message += f"\n\n🔗 [View in Odoo]({self._get_task_url()})"
            return message
        else:
            return f"📋 *Task Updated: {task.name}*\n\n🔗 [View in Odoo]({self._get_task_url()})"

    def _get_task_url(self):
        """Get Odoo URL for the task."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.task_id.id}&model=project.task&view_type=form"

    def action_view_messages(self):
        """Open messages view for this thread."""
        self.ensure_one()
        
        # TODO: Implement messages view
        # - Show recent messages from Google Chat
        # - Allow sending new messages
        _logger.info(f"Opening messages view for thread {self.thread_key}")
        pass

    @api.model
    def create_thread_for_task(self, task):
        """
        Create thread record for a task.
        
        Args:
            task: project.task record
            
        Returns:
            gchat.thread: Created thread record
        """
        # Find space for the task's project
        space = self.env['gchat.space'].search([
            ('project_id', '=', task.project_id.id),
            ('active', '=', True)
        ], limit=1)
        
        if not space:
            raise UserError(_('No Google Chat space configured for project %s') % task.project_id.name)
        
        # Create thread record
        thread = self.create({
            'task_id': task.id,
            'space_id': space.id,
            'thread_key': str(task.id),
            'thread_name': task.name
        })
        
        return thread 