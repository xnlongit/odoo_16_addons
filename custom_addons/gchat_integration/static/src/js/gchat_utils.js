odoo.define('gchat_integration.utils', function (require) {
    'use strict';

    var core = require('web.core');
    var _t = core._t;

    var GchatUtils = {
        /**
         * Format task update message for Google Chat
         * @param {Object} task - Task record
         * @param {Object} changes - Changed fields
         * @returns {string} Formatted message
         */
        formatTaskUpdateMessage: function (task, changes) {
            var message = '📋 *Task Updated: ' + task.name + '*\n\n';
            
            var fieldMapping = {
                'name': 'Name',
                'user_id': 'Assignee',
                'stage_id': 'Stage',
                'priority': 'Priority',
                'date_deadline': 'Deadline',
                'description': 'Description'
            };
            
            var changesList = [];
            for (var field in changes) {
                if (fieldMapping[field]) {
                    changesList.push('*' + fieldMapping[field] + '*: ' + changes[field]);
                }
            }
            
            if (changesList.length > 0) {
                message += changesList.join('\n');
            }
            
            return message;
        },

        /**
         * Show notification
         * @param {string} title - Notification title
         * @param {string} message - Notification message
         * @param {string} type - Notification type (success, warning, error, info)
         */
        showNotification: function (title, message, type) {
            core.bus.trigger('show_notification', {
                title: title,
                message: message,
                type: type || 'info',
                sticky: false
            });
        },

        /**
         * Validate Google Chat space ID format
         * @param {string} spaceId - Space ID to validate
         * @returns {boolean} True if valid
         */
        validateSpaceId: function (spaceId) {
            if (!spaceId) return false;
            
            // Google Chat space ID format: spaces/xxxxxxxxxx
            var spaceIdPattern = /^spaces\/[a-zA-Z0-9_-]+$/;
            return spaceIdPattern.test(spaceId);
        },

        /**
         * Generate thread key from task ID
         * @param {number} taskId - Task ID
         * @returns {string} Thread key
         */
        generateThreadKey: function (taskId) {
            return taskId.toString();
        }
    };

    return GchatUtils;
}); 