import json
import os


class Config:
    # Registries file path (the only registry-related env var)
    CONFIG_FILE = os.getenv("CONFIG_FILE", "/app/registries.config.json")

    # Registries loaded from CONFIG_FILE
    REGISTRIES = []

    # App runtime settings from environment
    READ_ONLY = os.getenv("READ_ONLY", "true").lower() == "true"
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
    TIMEOUT = int(os.getenv("TIMEOUT", "10"))
    BUILT_BY = os.getenv("BUILT_BY", "Vibhuvi OiO, molpie")

    # Persistent storage
    DB_PATH = os.getenv("DB_PATH", "/app/data/scan_results.db")

    # Daily massive scan scheduler
    MASSIVE_SCAN_SCHEDULE_ENABLED = (
        os.getenv("MASSIVE_SCAN_SCHEDULE_ENABLED", "false").lower() == "true"
    )
    # Cron expression for scheduling (defaults to daily 02:00 if empty)
    MASSIVE_SCAN_CRON_EXPRESSION = os.getenv("MASSIVE_SCAN_CRON_EXPRESSION", "")
    MASSIVE_SCAN_TIMEZONE = os.getenv("MASSIVE_SCAN_TIMEZONE", os.getenv("TZ", "local"))
    MASSIVE_SCAN_REGISTRIES = os.getenv("MASSIVE_SCAN_REGISTRIES", "all")
    MASSIVE_SCAN_REPO_PATTERN = os.getenv("MASSIVE_SCAN_REPO_PATTERN", "*")
    MASSIVE_SCAN_MODE = os.getenv("MASSIVE_SCAN_MODE", "all")
    MASSIVE_SCAN_AGE_VALUE = os.getenv("MASSIVE_SCAN_AGE_VALUE")
    MASSIVE_SCAN_AGE_UNIT = os.getenv("MASSIVE_SCAN_AGE_UNIT", "days")
    MASSIVE_SCAN_INCLUDE_ALL_TAGS = (
        os.getenv("MASSIVE_SCAN_INCLUDE_ALL_TAGS", "true").lower() == "true"
    )
    MASSIVE_SCAN_DRY_RUN = os.getenv("MASSIVE_SCAN_DRY_RUN", "false").lower() == "true"

    # Notifications - email
    NOTIFY_EMAIL_ENABLED = os.getenv("NOTIFY_EMAIL_ENABLED", "false").lower() == "true"
    NOTIFY_EMAIL_SMTP_HOST = os.getenv("NOTIFY_EMAIL_SMTP_HOST", "")
    NOTIFY_EMAIL_SMTP_PORT = int(os.getenv("NOTIFY_EMAIL_SMTP_PORT", "587"))
    NOTIFY_EMAIL_USE_TLS = os.getenv("NOTIFY_EMAIL_USE_TLS", "true").lower() == "true"
    NOTIFY_EMAIL_SMTP_USER = os.getenv("NOTIFY_EMAIL_SMTP_USER", "")
    NOTIFY_EMAIL_SMTP_PASSWORD = os.getenv("NOTIFY_EMAIL_SMTP_PASSWORD", "")
    NOTIFY_EMAIL_FROM = os.getenv("NOTIFY_EMAIL_FROM", "")
    NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")

    # Notifications - Telegram
    NOTIFY_TELEGRAM_ENABLED = (
        os.getenv("NOTIFY_TELEGRAM_ENABLED", "false").lower() == "true"
    )
    NOTIFY_TELEGRAM_BOT_TOKEN = os.getenv("NOTIFY_TELEGRAM_BOT_TOKEN", "")
    NOTIFY_TELEGRAM_CHAT_ID = os.getenv("NOTIFY_TELEGRAM_CHAT_ID", "")


    # Only send notifications if there is a positive delta (>0) in vulnerabilities
    NOTIFY_ONLY_IF_DELTA_GT_0 = (
        os.getenv("NOTIFY_ONLY_IF_DELTA_GT_0", "false").lower() == "true"
    )

    @staticmethod
    def load_registries():
        """Load registries from CONFIG_FILE only."""
        if os.path.exists(Config.CONFIG_FILE):
            try:
                with open(Config.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Preferred format: {"registries": [...]} ; legacy: [...]
                if isinstance(data, dict):
                    registries = data.get("registries", [])
                    Config.REGISTRIES = (
                        registries if isinstance(registries, list) else []
                    )
                elif isinstance(data, list):
                    Config.REGISTRIES = data
                else:
                    Config.REGISTRIES = []
            except Exception as e:
                print(f"Failed to load config: {e}")
                Config.REGISTRIES = []

        if not Config.REGISTRIES:
            Config.REGISTRIES = []

        return Config.REGISTRIES

    @staticmethod
    def save_registries():
        """Save registries only to CONFIG_FILE."""
        try:
            payload = {"registries": Config.REGISTRIES}
            with open(Config.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False


# Load registries on import
Config.load_registries()
