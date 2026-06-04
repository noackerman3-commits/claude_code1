"""
Configuration management for the rental agent.
"""
import yaml
from typing import Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = None

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"Configuration file not found: {self.config_path}")
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)

            self._apply_env_overrides()
            logger.info("Configuration loaded successfully")
            return self.config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def _apply_env_overrides(self):
        """Override sensitive values and CI-specific settings from environment variables."""
        if 'telegram' not in self.config:
            self.config['telegram'] = {}

        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if bot_token:
            self.config['telegram']['bot_token'] = bot_token
        if chat_id:
            self.config['telegram']['chat_id'] = chat_id

        # Force headless mode in CI environments (GitHub Actions sets CI=true)
        if os.environ.get('CI'):
            if 'browser' not in self.config:
                self.config['browser'] = {}
            self.config['browser']['headless'] = True

    def save_config(self, config: Dict[str, Any]):
        """Save configuration to YAML file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            self.config = config
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise

    def validate_config(self) -> bool:
        """Validate configuration parameters."""
        if not self.config:
            logger.error("No configuration loaded")
            return False

        required_sections = ['search_parameters', 'sources', 'telegram', 'scraping', 'browser', 'database']

        for section in required_sections:
            if section not in self.config:
                logger.error(f"Missing required configuration section: {section}")
                return False

        # Validate Telegram configuration
        telegram = self.config.get('telegram', {})
        if not telegram.get('bot_token') or telegram.get('bot_token') == 'YOUR_BOT_TOKEN':
            logger.error("Telegram bot token not configured")
            return False

        if not telegram.get('chat_id') or telegram.get('chat_id') == 'YOUR_CHAT_ID':
            logger.error("Telegram chat ID not configured")
            return False

        # Validate search parameters
        search_params = self.config.get('search_parameters', {})
        price_range = search_params.get('price_range', {})

        if price_range.get('min', 0) > price_range.get('max', 0):
            logger.error("Invalid price range: min > max")
            return False

        logger.info("Configuration validation passed")
        return True

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        if not self.config:
            self.load_config()

        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default

        return value
