"""
SMS Providers - Platform-agnostic SMS sending with pluggable providers.

Supported providers:
- textbelt: International SMS via textbelt.com
- iletimerkezi: Turkish SMS provider via iletimerkezi.com
- twilio: Global SMS via twilio.com

Configuration:
- Primary: instance/sms_config.json
- Fallback: Environment variables
"""

import logging
from abc import ABC, abstractmethod

import requests

from sms_config import get_sms_config

logger = logging.getLogger(__name__)


class SMSProvider(ABC):
    """Abstract base class for SMS providers."""
    
    @abstractmethod
    def send(self, phone: str, message: str) -> bool:
        """Send SMS to phone number. Returns True on success."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return provider name for logging."""
        pass


class TextbeltProvider(SMSProvider):
    """
    Textbelt SMS provider.
    API docs: https://textbelt.com/
    
    Config keys:
    - textbelt.api_key: Your API key (use 'textbelt' for free tier - 1 SMS/day)
    """
    
    API_URL = "https://textbelt.com/text"
    
    def __init__(self):
        self.api_key = get_sms_config("textbelt.api_key", "textbelt")
    
    def get_name(self) -> str:
        return "Textbelt"
    
    def send(self, phone: str, message: str) -> bool:
        try:
            response = requests.post(self.API_URL, data={
                "phone": phone,
                "message": message,
                "key": self.api_key
            }, timeout=30)
            
            result = response.json()
            if result.get("success"):
                logger.info(f"Textbelt SMS sent to {phone}, ID: {result.get('textId')}")
                return True
            else:
                logger.error(f"Textbelt SMS failed: {result.get('error')}")
                return False
        except Exception as e:
            logger.error(f"Textbelt SMS error: {e}")
            return False


class IletimerkeziProvider(SMSProvider):
    """
    İleti Merkezi SMS provider (Turkish).
    API docs: https://www.toplusmsapi.com/sms/gonder/get
    
    Config keys:
    - iletimerkezi.api_key: Your API key
    - iletimerkezi.api_hash: Your API hash
    - iletimerkezi.sender: Approved sender ID
    """
    
    API_URL = "https://api.iletimerkezi.com/v1/send-sms/get/"
    
    def __init__(self):
        self.api_key = get_sms_config("iletimerkezi.api_key", "")
        self.api_hash = get_sms_config("iletimerkezi.api_hash", "")
        self.sender = get_sms_config("iletimerkezi.sender", "")
    
    def get_name(self) -> str:
        return "İleti Merkezi"
    
    def send(self, phone: str, message: str) -> bool:
        if not all([self.api_key, self.api_hash, self.sender]):
            logger.error("İleti Merkezi: Missing API credentials")
            return False
        
        # Remove + and country code prefix, use 10-digit Turkish number
        phone_clean = phone.lstrip("+")
        if phone_clean.startswith("90"):
            phone_clean = phone_clean[2:]  # Remove 90 prefix
        
        params = {
            "key": self.api_key,
            "hash": self.api_hash,
            "text": message,
            "receipents": phone_clean,
            "sender": self.sender,
            "iys": "0"  # Skip IYS check for non-commercial messages
        }
        
        try:
            response = requests.get(self.API_URL, params=params, timeout=30)
            
            # Check if response contains success indicator
            if response.status_code == 200 and "200" in response.text:
                logger.info(f"İleti Merkezi SMS sent to {phone}")
                return True
            else:
                logger.error(f"İleti Merkezi SMS failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"İleti Merkezi SMS error: {e}")
            return False


class TwilioProvider(SMSProvider):
    """
    Twilio SMS provider.
    API docs: https://www.twilio.com/docs/sms/api
    
    Config keys:
    - twilio.account_sid: Your Twilio Account SID
    - twilio.auth_token: Your Twilio Auth Token
    - twilio.from_number: Your Twilio phone number (E.164 format)
    """
    
    API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    
    def __init__(self):
        self.account_sid = get_sms_config("twilio.account_sid", "")
        self.auth_token = get_sms_config("twilio.auth_token", "")
        self.from_number = get_sms_config("twilio.from_number", "")
    
    def get_name(self) -> str:
        return "Twilio"
    
    def send(self, phone: str, message: str) -> bool:
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.error("Twilio: Missing API credentials")
            return False
        
        url = self.API_URL.format(sid=self.account_sid)
        
        try:
            response = requests.post(
                url,
                data={
                    "To": phone,
                    "From": self.from_number,
                    "Body": message
                },
                auth=(self.account_sid, self.auth_token),
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Twilio SMS sent to {phone}, SID: {result.get('sid')}")
                return True
            else:
                logger.error(f"Twilio SMS failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Twilio SMS error: {e}")
            return False


class DisabledProvider(SMSProvider):
    """Dummy provider when SMS is disabled."""
    
    def get_name(self) -> str:
        return "Disabled"
    
    def send(self, phone: str, message: str) -> bool:
        logger.debug(f"SMS disabled. Would send to {phone}: {message}")
        return True


def get_sms_provider() -> SMSProvider:
    """Factory function to get the configured SMS provider."""
    provider_name = get_sms_config("provider", "disabled").lower()
    
    providers = {
        "textbelt": TextbeltProvider,
        "iletimerkezi": IletimerkeziProvider,
        "twilio": TwilioProvider,
        "disabled": DisabledProvider,
    }
    
    provider_class = providers.get(provider_name, DisabledProvider)
    return provider_class()


def send_sms(phone: str, message: str) -> bool:
    """
    Send SMS using the configured provider.
    
    Args:
        phone: Phone number in E.164 format (e.g., +905551234567)
        message: SMS message text
    
    Returns:
        True if sent successfully, False otherwise
    """
    provider = get_sms_provider()
    logger.info(f"Sending SMS via {provider.get_name()} to {phone}")
    return provider.send(phone, message)

