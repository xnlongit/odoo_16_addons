# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    gchat_thread_id = fields.Many2one('gchat.thread', string='Google Chat Thread', 
                                     compute='_compute_gchat_thread', store=True)
    
    # Computed fields for UI
    has_gchat_thread = fields.Boolean('Has Google Chat Thread', compute='_compute_has_gchat_thread')
    gchat_thread_key = fields.Char('Thread Key', compute='_compute_gchat_thread_key')

    @api.depends('project_id.gchat_sync_enabled')
    def _compute_gchat_thread(self):
        """Compute the associated Google Chat thread."""
        for task in self:
            if task.project_id.gchat_sync_enabled:
                thread = self.env['gchat.thread'].search([
                    ('task_id', '=', task.id),
                    ('active', '=', True)
                ], limit=1)
                task.gchat_thread_id = thread
            else:
                task.gchat_thread_id = False

    @api.depends('gchat_thread_id')
    def _compute_has_gchat_thread(self):
        """Compute if task has a Google Chat thread."""
        for task in self:
            task.has_gchat_thread = bool(task.gchat_thread_id)

    @api.depends('gchat_thread_id.thread_key')
    def _compute_gchat_thread_key(self):
        """Compute the thread key."""
        for task in self:
            task.gchat_thread_key = task.gchat_thread_id.thread_key if task.gchat_thread_id else ''

    @api.model
    def create(self, vals):
        """Override create to handle Google Chat integration."""
        task = super().create(vals)
        
        # Create Google Chat thread if project has sync enabled
        if task.project_id.gchat_sync_enabled:
            try:
                thread = self.env['gchat.thread'].create_thread_for_task(task)
                _logger.info(f"Created Google Chat thread for task {task.name}")
                
                # Send initial message to thread
                if thread:
                    thread.push_task_update({'name': task.name})
                    
            except Exception as e:
                _logger.error(f"Failed to create Google Chat thread for task {task.name}: {str(e)}")
        
        return task

    def write(self, vals):
        """Override write to handle Google Chat integration."""
        # Track changes for Google Chat notification
        changes_to_notify = {}
        important_fields = ['name', 'user_id', 'stage_id', 'priority', 'date_deadline', 'description']
        
        for field in important_fields:
            if field in vals:
                changes_to_notify[field] = vals[field]
        
        result = super().write(vals)
        
        # Send notification to Google Chat if there are important changes
        if changes_to_notify and self.gchat_thread_id:
            try:
                self.gchat_thread_id.push_task_update(changes_to_notify)
                _logger.info(f"Sent Google Chat notification for task {self.name}")
            except Exception as e:
                _logger.error(f"Failed to send Google Chat notification for task {self.name}: {str(e)}")
        
        return result

    def action_view_gchat_thread(self):
        """Open Google Chat thread view."""
        self.ensure_one()
        
        if not self.gchat_thread_id:
            raise UserError(_('No Google Chat thread linked to this task.'))
        
        return {
            'name': _('Google Chat Thread'),
            'type': 'ir.actions.act_window',
            'res_model': 'gchat.thread',
            'res_id': self.gchat_thread_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_send_gchat_message(self):
        """Open wizard to send message to Google Chat thread."""
        self.ensure_one()
        
        if not self.gchat_thread_id:
            raise UserError(_('No Google Chat thread linked to this task.'))
        
        return {
            'name': _('Send Google Chat Message'),
            'type': 'ir.actions.act_window',
            'res_model': 'gchat.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
                'default_thread_id': self.gchat_thread_id.id,
            }
        }

    def action_create_gchat_thread(self):
        """Create Google Chat thread for this task."""
        self.ensure_one()
        
        if not self.project_id.gchat_sync_enabled:
            raise UserError(_('Google Chat sync is not enabled for this project.'))
        
        if self.gchat_thread_id:
            raise UserError(_('Google Chat thread already exists for this task.'))
        
        try:
            thread = self.env['gchat.thread'].create_thread_for_task(self)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Google Chat thread created successfully'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to create Google Chat thread: %s') % str(e))

    def action_sync_gchat_thread(self):
        """Sync task with Google Chat thread."""
        self.ensure_one()
        
        if not self.gchat_thread_id:
            raise UserError(_('No Google Chat thread linked to this task.'))
        
        try:
            # Send current task state to Google Chat
            current_state = {
                'name': self.name,
                'user_id': self.user_id.id if self.user_id else False,
                'stage_id': self.stage_id.id if self.stage_id else False,
                'priority': self.priority,
                'date_deadline': self.date_deadline,
                'description': self.description,
            }
            
            self.gchat_thread_id.push_task_update(current_state)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Task synced with Google Chat successfully'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Failed to sync with Google Chat: %s') % str(e)) 