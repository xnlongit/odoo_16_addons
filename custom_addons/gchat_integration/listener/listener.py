#!/usr/bin/env python3
"""
Google Chat Pub/Sub Listener for Odoo Integration

This script pulls messages from Google Cloud Pub/Sub and forwards them to Odoo webhook.
"""

import argparse
import base64
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Any

import requests
from google.cloud import pubsub_v1
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GchatListener:
    """Google Chat Pub/Sub listener for Odoo integration."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the listener with configuration."""
        self.config = config
        self.subscriber = None
        self.odoo_session = requests.Session()
        
        # Set up Odoo session headers
        self.odoo_session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config["webhook_token"]}'
        })
        
        # Initialize Pub/Sub subscriber
        self._setup_subscriber()
    
    def _setup_subscriber(self):
        """Set up Google Cloud Pub/Sub subscriber."""
        try:
            if self.config.get('sa_json_path'):
                # Use service account JSON file
                credentials = service_account.Credentials.from_service_account_file(
                    self.config['sa_json_path']
                )
                self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
            else:
                # Use default credentials
                self.subscriber = pubsub_v1.SubscriberClient()
                
            logger.info("Pub/Sub subscriber initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Pub/Sub subscriber: {e}")
            raise
    
    def _format_webhook_payload(self, message) -> Dict[str, Any]:
        """Format Pub/Sub message for Odoo webhook."""
        try:
            # Decode message data
            data = message.data.decode('utf-8')
            event_json = json.loads(data)
            
            # Format payload for Odoo webhook
            payload = {
                'message_id': message.message_id,
                'publish_time': message.publish_time.isoformat(),
                'attributes': dict(message.attributes),
                'data_base64': base64.b64encode(message.data).decode('utf-8')
            }
            
            return payload
            
        except Exception as e:
            logger.error(f"Failed to format webhook payload: {e}")
            raise
    
    def _send_to_odoo(self, payload: Dict[str, Any]) -> bool:
        """Send payload to Odoo webhook."""
        try:
            url = f"{self.config['odoo_url']}{self.config['webhook_path']}"
            
            response = self.odoo_session.post(
                url,
                json=payload,
                timeout=self.config.get('timeout', 30)
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent message {payload['message_id']} to Odoo")
                return True
            else:
                logger.error(f"Failed to send message to Odoo: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error sending to Odoo: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to Odoo: {e}")
            return False
    
    def _process_message(self, message):
        """Process a single Pub/Sub message."""
        try:
            logger.info(f"Processing message {message.message_id}")
            
            # Format payload for Odoo
            payload = self._format_webhook_payload(message)
            
            # Send to Odoo webhook
            success = self._send_to_odoo(payload)
            
            if success:
                # Acknowledge message
                message.ack()
                logger.info(f"Message {message.message_id} processed successfully")
            else:
                # Negative acknowledgment - message will be retried
                message.nack()
                logger.warning(f"Message {message.message_id} failed, will retry")
                
        except Exception as e:
            logger.error(f"Error processing message {message.message_id}: {e}")
            # Negative acknowledgment on error
            message.nack()
    
    def _message_callback(self, message):
        """Callback function for received messages."""
        try:
            self._process_message(message)
        except Exception as e:
            logger.error(f"Error in message callback: {e}")
            message.nack()
    
    def start_listening(self):
        """Start listening for Pub/Sub messages."""
        try:
            subscription_path = self.subscriber.subscription_path(
                self.config['gcp_project'],
                self.config['subscription_name']
            )
            
            logger.info(f"Starting to listen on subscription: {subscription_path}")
            
            # Start the subscriber
            streaming_pull_future = self.subscriber.subscribe(
                subscription_path,
                callback=self._message_callback,
                flow_control=pubsub_v1.types.FlowControl(
                    max_messages=self.config.get('max_messages', 50)
                )
            )
            
            logger.info(f"Listening for messages on {subscription_path}")
            
            try:
                # Keep the main thread alive
                streaming_pull_future.result()
            except KeyboardInterrupt:
                streaming_pull_future.cancel()
                logger.info("Shutting down listener...")
                
        except Exception as e:
            logger.error(f"Error starting listener: {e}")
            raise
    
    def stop(self):
        """Stop the listener."""
        if self.subscriber:
            self.subscriber.close()
            logger.info("Listener stopped")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Google Chat Pub/Sub Listener for Odoo')
    
    parser.add_argument('--gcp-project', required=True,
                       help='Google Cloud Project ID')
    parser.add_argument('--subscription', required=True,
                       help='Pub/Sub subscription name')
    parser.add_argument('--sa-json', 
                       help='Path to service account JSON file')
    parser.add_argument('--odoo-url', required=True,
                       help='Odoo base URL (e.g., https://your-odoo.com)')
    parser.add_argument('--webhook', default='/gchat/webhook',
                       help='Webhook path (default: /gchat/webhook)')
    parser.add_argument('--token', required=True,
                       help='Webhook authentication token')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--max-messages', type=int, default=50,
                       help='Maximum messages to process concurrently (default: 50)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_arguments()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Configuration
    config = {
        'gcp_project': args.gcp_project,
        'subscription_name': args.subscription,
        'sa_json_path': args.sa_json,
        'odoo_url': args.odoo_url.rstrip('/'),
        'webhook_path': args.webhook,
        'webhook_token': args.token,
        'timeout': args.timeout,
        'max_messages': args.max_messages
    }
    
    logger.info("Starting Google Chat Pub/Sub Listener")
    logger.info(f"Project: {config['gcp_project']}")
    logger.info(f"Subscription: {config['subscription_name']}")
    logger.info(f"Odoo URL: {config['odoo_url']}")
    
    listener = None
    try:
        # Create and start listener
        listener = GchatListener(config)
        listener.start_listening()
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        if listener:
            listener.stop()


if __name__ == '__main__':
    main() 