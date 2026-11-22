"""Errors raised by the ShelfScout engine. All derive from ShelfScoutError."""


class ShelfScoutError(Exception):
    """Base class for engine errors."""


class UnitError(ShelfScoutError):
    """Unknown unit, or a comparison/conversion between incompatible dimensions."""


class CurrencyError(ShelfScoutError):
    """Invalid currency code, or arithmetic across currencies without an exchange rate."""


class EvidenceError(ShelfScoutError):
    """An evidence record breaks a provenance rule."""


class ProfileError(ShelfScoutError):
    """A category scoring profile is invalid."""


class ValidationError(ShelfScoutError):
    """A model field has an invalid value."""
