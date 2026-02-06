"""Configuration hot-reload support."""

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class ConfigReloader:
    """Hot-reload configuration from file.

    Watches configuration file for changes and triggers reload callbacks.
    """

    def __init__(
        self,
        config_path: str | Path,
        on_reload: Callable[[dict[str, Any]], None] | None = None,
        poll_interval: float = 1.0,
    ) -> None:
        """Initialize config reloader.

        Args:
            config_path: Path to config file (JSON or YAML)
            on_reload: Callback when config changes
            poll_interval: File poll interval in seconds
        """
        self.config_path = Path(config_path)
        self.on_reload = on_reload
        self.poll_interval = poll_interval
        self._last_mtime: float = 0.0
        self._last_content: str = ""
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start watching for config changes."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("config_reloader.started", path=str(self.config_path))

    def stop(self) -> None:
        """Stop watching for config changes."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("config_reloader.stopped")

    def _watch_loop(self) -> None:
        """Main watch loop."""
        while self._running:
            try:
                self._check_and_reload()
            except Exception as e:
                logger.error("config_reloader.check_failed", error=str(e))
            time.sleep(self.poll_interval)

    def _check_and_reload(self) -> None:
        """Check if config changed and reload if needed."""
        if not self.config_path.exists():
            return

        try:
            mtime = self.config_path.stat().st_mtime
            if mtime == self._last_mtime:
                return

            with open(self.config_path, "r") as f:
                content = f.read()

            if content == self._last_content:
                self._last_mtime = mtime
                return

            # Parse config
            config = self._parse_config(content)
            if config is None:
                logger.warning("config_reloader.parse_failed")
                return

            with self._lock:
                self._last_mtime = mtime
                self._last_content = content

            logger.info("config_reloader.detected_change", path=str(self.config_path))

            if self.on_reload:
                try:
                    self.on_reload(config)
                    logger.info("config_reloader.reload_success")
                except Exception as e:
                    logger.error("config_reloader.reload_failed", error=str(e))

        except Exception as e:
            logger.error("config_reloader.check_error", error=str(e))

    def _parse_config(self, content: str) -> dict[str, Any] | None:
        """Parse config content.

        Args:
            content: File content

        Returns:
            Parsed config dict or None
        """
        try:
            # Try JSON first
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try YAML
        try:
            import yaml

            return yaml.safe_load(content)
        except ImportError:
            logger.error("config_reloader.yaml_not_installed")
        except Exception as e:
            logger.error("config_reloader.yaml_parse_failed", error=str(e))

        return None

    def force_reload(self) -> dict[str, Any] | None:
        """Force reload config immediately.

        Returns:
            Reloaded config or None if failed
        """
        if not self.config_path.exists():
            logger.error("config_reloader.file_not_found", path=str(self.config_path))
            return None

        try:
            with open(self.config_path, "r") as f:
                content = f.read()

            config = self._parse_config(content)
            if config is None:
                return None

            with self._lock:
                self._last_mtime = self.config_path.stat().st_mtime
                self._last_content = content

            if self.on_reload:
                self.on_reload(config)

            return config
        except Exception as e:
            logger.error("config_reloader.force_reload_failed", error=str(e))
            return None


class ConfigManager:
    """Manages configuration with hot-reload support."""

    def __init__(self) -> None:
        """Initialize config manager."""
        self._config: dict[str, Any] = {}
        self._reloader: ConfigReloader | None = None
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []

    def load_from_file(
        self,
        config_path: str | Path,
        auto_reload: bool = True,
    ) -> dict[str, Any] | None:
        """Load config from file with optional hot-reload.

        Args:
            config_path: Path to config file
            auto_reload: Enable auto-reload on changes

        Returns:
            Loaded config or None
        """
        config_path = Path(config_path)
        if not config_path.exists():
            logger.warning("config_manager.file_not_found", path=str(config_path))
            return None

        try:
            with open(config_path, "r") as f:
                content = f.read()

            # Try JSON
            try:
                self._config = json.loads(content)
            except json.JSONDecodeError:
                # Try YAML
                import yaml

                self._config = yaml.safe_load(content)

            if auto_reload:
                self._reloader = ConfigReloader(
                    config_path,
                    on_reload=self._on_config_change,
                )
                self._reloader.start()

            logger.info("config_manager.loaded", path=str(config_path))
            return self._config

        except Exception as e:
            logger.error("config_manager.load_failed", error=str(e))
            return None

    def _on_config_change(self, new_config: dict[str, Any]) -> None:
        """Handle config change.

        Args:
            new_config: New configuration
        """
        old_config = self._config
        self._config = new_config

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(new_config, old_config)
            except Exception as e:
                logger.error("config_manager.callback_error", error=str(e))

    def register_callback(
        self, callback: Callable[[dict[str, Any], dict[str, Any]], None]
    ) -> None:
        """Register callback for config changes.

        Args:
            callback: Function(new_config, old_config)
        """
        self._callbacks.append(callback)

    def unregister_callback(
        self, callback: Callable[[dict[str, Any], dict[str, Any]], None]
    ) -> bool:
        """Unregister callback.

        Args:
            callback: Callback to remove

        Returns:
            True if removed
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            return True
        return False

    def force_reload(self) -> dict[str, Any] | None:
        """Force reload config.

        Returns:
            Reloaded config or None
        """
        if self._reloader:
            return self._reloader.force_reload()
        return None

    def get_config(self) -> dict[str, Any]:
        """Get current config.

        Returns:
            Current configuration
        """
        return self._config.copy()

    def stop(self) -> None:
        """Stop config reloader."""
        if self._reloader:
            self._reloader.stop()


# Global config manager instance
_global_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get global config manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = ConfigManager()
    return _global_manager
