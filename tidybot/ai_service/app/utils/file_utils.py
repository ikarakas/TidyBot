import re

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize filename for filesystem compatibility"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    filename = re.sub(r'_+', '_', filename)
    filename = filename.strip('_. ')
    if len(filename) > max_length:
        name_parts = filename.rsplit('.', 1)
        if len(name_parts) == 2:
            name, ext = name_parts
            max_name_length = max_length - len(ext) - 1
            filename = f"{name[:max_name_length]}.{ext}"
        else:
            filename = filename[:max_length]
    return filename or "unnamed"
