from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Return dictionary[key] (works with dicts and objects with attributes)."""
    try:
        if isinstance(dictionary, dict):
            return dictionary.get(key)
        # allow attribute access for objects
        return getattr(dictionary, key)
    except Exception:
        return None


@register.filter
def split(value, sep=None):
    """Split a string by sep (default comma). Usage: {{ "a,b"|split:"," }}"""
    if value is None:
        return []
    if sep is None:
        sep = ','
    try:
        return [v.strip() for v in str(value).split(sep)]
    except Exception:
        return []
