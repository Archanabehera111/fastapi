import re

def snake_case(string):
    # Remove newlines and extra spaces/tabs
    string = re.sub(r'\s+', ' ', string.strip())
    # Convert to snake_case
    string = re.sub(r'(?<!^)(?=[A-Z])', '_', string).lower()
    # Replace spaces with underscores
    string = string.replace(' ', '_')
    string = re.sub(r'[_]+', '_', string)
    return string
