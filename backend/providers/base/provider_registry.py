# providers/base/provider_registry.py
"""
Provider Registry - Registry Pattern + Open/Closed Principle.

How it works:
  1. Each provider module calls ProviderRegistry.register() on import
  2. discover_providers() imports all provider modules (triggers registration)
  3. Orchestrator calls ProviderRegistry.create(name) - no concrete imports

Adding a new provider requires ZERO changes to this file or the orchestrator.
Only the new provider/provider.py needs to be created and self-register.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, Optional, Tuple, Type, List, TYPE_CHECKING

if TYPE_CHECKING:
    from providers.base.abstract_provider import AbstractDataProvider, AbstractDataTransformer

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Global registry mapping provider name → (ProviderClass, TransformerClass).

    Thread-safe for reads; writes happen only at import time (module load).
    """

    # Internal registry: name → (ProviderClass, TransformerClass)
    _registry: Dict[str, Tuple[Type, Type]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        provider_class: Type,
        transformer_class: Type,
    ) -> None:
        """
        Register a provider + transformer pair.

        Args:
            name:              Unique provider identifier (e.g. 'sofascore').
            provider_class:    Class implementing AbstractDataProvider.
            transformer_class: Class implementing AbstractDataTransformer.

        Raises:
            ValueError: If name is already registered with a DIFFERENT class.
                        Re-registering with the same class is a no-op (safe).
        """
        existing = cls._registry.get(name)
        if existing:
            if existing == (provider_class, transformer_class):
                return  # idempotent re-registration - safe
            raise ValueError(
                f"Provider '{name}' is already registered with a different class. "
                f"Existing: {existing[0].__name__}. "
                f"New: {provider_class.__name__}. "
                "Unregister the existing provider first."
            )
        cls._registry[name] = (provider_class, transformer_class)
        logger.debug(
            "ProviderRegistry: registered '%s' → (%s, %s)",
            name, provider_class.__name__, transformer_class.__name__,
        )

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove a provider from the registry. Useful for testing."""
        cls._registry.pop(name, None)

    @classmethod
    def create(cls, name: str, config) -> "AbstractDataProvider":
        """
        Instantiate and return a provider by name.

        Args:
            name:   Provider identifier.
            config: ConfigManager instance passed to provider constructor.

        Returns:
            Concrete AbstractDataProvider instance.

        Raises:
            KeyError: If provider is not registered.
        """
        entry = cls._registry.get(name)
        if not entry:
            raise KeyError(
                f"Provider '{name}' is not registered. "
                f"Available: {cls.available_providers()}. "
                "Did you call discover_providers() first?"
            )
        provider_class, _ = entry
        return provider_class(config)

    @classmethod
    def create_transformer(cls, name: str) -> "AbstractDataTransformer":
        """
        Instantiate and return a transformer by provider name.

        Returns:
            Concrete AbstractDataTransformer instance (stateless, no config).

        Raises:
            KeyError: If provider is not registered.
        """
        entry = cls._registry.get(name)
        if not entry:
            raise KeyError(
                f"No transformer registered for provider '{name}'. "
                f"Available: {cls.available_providers()}."
            )
        _, transformer_class = entry
        return transformer_class()

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a provider is registered."""
        return name in cls._registry

    @classmethod
    def available_providers(cls) -> List[str]:
        """Return sorted list of registered provider names."""
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations. Use only in tests."""
        cls._registry.clear()


def discover_providers() -> List[str]:
    """
    Auto-discover and import all provider modules.

    Scans the providers/ package for sub-packages and imports
    `providers.<name>.provider` from each.  The import side-effect
    triggers each module's self-registration call.

    Returns:
        List of successfully discovered provider names.
    """
    import providers as providers_pkg

    discovered: List[str] = []

    for importer, subpkg_name, is_pkg in pkgutil.iter_modules(providers_pkg.__path__):
        if not is_pkg or subpkg_name == "base":
            continue  # skip non-packages and the base package itself

        module_path = f"providers.{subpkg_name}.provider"
        try:
            importlib.import_module(module_path)
            discovered.append(subpkg_name)
            logger.debug("discover_providers: imported '%s'", module_path)
        except ImportError as exc:
            logger.warning(
                "discover_providers: could not import '%s': %s",
                module_path, exc,
            )
        except Exception as exc:
            logger.error(
                "discover_providers: error loading '%s': %s",
                module_path, exc, exc_info=True,
            )

    logger.info(
        "discover_providers: found %d providers: %s",
        len(discovered), discovered,
    )
    return discovered
