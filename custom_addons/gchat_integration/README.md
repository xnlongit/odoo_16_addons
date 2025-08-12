# Google Chat Integration for Odoo 16

This module provides seamless integration between Odoo 16 projects and Google Chat spaces, enabling real-time communication and task management.

## Features

- **Project ↔ Space Mapping**: Link Odoo projects to Google Chat spaces
- **Task ↔ Thread Synchronization**: Automatically create threads for tasks and sync updates
- **Outbound Notifications**: Send task updates to Google Chat
- **Inbound Webhook Support**: Receive Google Chat messages in Odoo
- **Pub/Sub Integration**: Real-time event processing via Google Cloud Pub/Sub
- **Multi-company Support**: Separate configurations per company
- **Member Management**: Sync and manage space members

## Architecture

```
Odoo Project ↔ Google Chat Space
Odoo Task ↔ Google Chat Thread (thread_key = task.id)
```

### Outbound Flow (Odoo → Chat)
- Task creation/updates trigger notifications
- Messages sent to appropriate thread in Google Chat
- Support for text and card messages

### Inbound Flow (Chat → Odoo)
- Google Chat events via Pub/Sub
- Python listener processes events
- Messages appear in task chatter
- Member management integration

## Installation

1. Copy the module to your Odoo addons directory
2. Update the addons list in Odoo
3. Install the "Google Chat Integration" module
4. Configure Google Chat settings

## Configuration

### 1. Google Chat Configuration

Navigate to **Google Chat > Configuration > Connections** and create a new configuration:

- **Authentication Mode**: Choose between Service Account or OAuth 2.0
- **Service Account**: Upload JSON key file
- **OAuth 2.0**: Provide Client ID and Secret
- **Webhook Token**: Generate a secure token for webhook authentication

### 2. Project Setup

1. Open a project
2. Click "Sync with Google Chat"
3. Choose to create a new space or link existing one
4. Enable sync for the project

### 3. Listener Setup (for inbound messages)

1. Install Python dependencies:
   ```bash
   cd custom_addons/gchat_integration/listener
   pip install -r requirements.txt
   ```

2. Configure the systemd service:
   ```bash
   # Edit the service file
   sudo nano /etc/systemd/system/gchat-listener.service
   
   # Update the ExecStart line with your configuration
   ExecStart=/usr/bin/python3 /path/to/listener.py \
       --gcp-project YOUR_PROJECT_ID \
       --subscription YOUR_SUBSCRIPTION_NAME \
       --sa-json /path/to/service-account.json \
       --odoo-url https://your-odoo.com \
       --token YOUR_WEBHOOK_TOKEN
   
   # Enable and start the service
   sudo systemctl daemon-reload
   sudo systemctl enable gchat-listener
   sudo systemctl start gchat-listener
   ```

## Usage

### Project Integration

1. **Create/Link Space**: Use the "Sync with Google Chat" button on projects
2. **View Threads**: Access all task threads for a project
3. **Member Management**: Sync and manage space members

### Task Integration

1. **Automatic Thread Creation**: Threads are created when tasks are synced
2. **Update Notifications**: Task changes are automatically posted to Google Chat
3. **Manual Messages**: Send custom messages to task threads
4. **Thread Viewing**: View and manage individual task threads

### Event Monitoring

- **Events Log**: Monitor all incoming Google Chat events
- **Processing Status**: Track event processing status
- **Error Handling**: Retry failed event processing

## Models

### Core Models

- `gchat.config`: Google Chat configuration and authentication
- `gchat.space`: Project ↔ Space mapping
- `gchat.thread`: Task ↔ Thread mapping
- `gchat.subscription`: Pub/Sub subscription management
- `gchat.member`: Space member management
- `gchat.event.log`: Event processing and logging

### Inherited Models

- `project.project`: Added Google Chat integration fields and actions
- `project.task`: Added thread management and notification features

## API Endpoints

### Webhook Endpoint
- **URL**: `/gchat/webhook`
- **Method**: POST
- **Authentication**: Bearer token
- **Purpose**: Receive Google Chat events

### Health Check
- **URL**: `/gchat/webhook/health`
- **Method**: GET
- **Purpose**: Monitor webhook health

## Security

- **Multi-company**: All data is company-scoped
- **Access Control**: Separate user and manager groups
- **Webhook Authentication**: Token-based authentication
- **Encrypted Storage**: Sensitive data is encrypted

## Development

### Adding New Event Types

1. Extend the `_process_message_*` methods in `gchat.event.log`
2. Add new event type handling logic
3. Update the event routing in `process_incoming`

### Custom Message Formats

1. Modify the `_format_task_update_message` method in `gchat.thread`
2. Add new field mappings as needed
3. Customize message templates

### Extending API Integration

1. Implement Google API calls in the respective models
2. Add error handling and retry logic
3. Update configuration as needed

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Check service account permissions or OAuth configuration
2. **Webhook Failures**: Verify webhook token and URL accessibility
3. **Listener Issues**: Check Pub/Sub subscription and service account permissions
4. **Sync Problems**: Verify project and space configuration

### Logs

- **Odoo Logs**: Check Odoo server logs for integration errors
- **Listener Logs**: Use `journalctl -u gchat-listener` for listener logs
- **Event Logs**: Monitor the Events Log in Odoo interface

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This module is licensed under LGPL-3.

## Support

For support and questions:
- Check the troubleshooting section
- Review the logs for error details
- Ensure all dependencies are properly installed
- Verify Google Cloud configuration

## Roadmap

- [ ] Google Tasks integration
- [ ] Advanced message formatting
- [ ] Bulk operations
- [ ] Analytics and reporting
- [ ] Mobile app integration 