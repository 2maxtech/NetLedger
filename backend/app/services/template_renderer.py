def render_template(template: str, variables: dict) -> str:
    """Render a notification template with variable substitution.
    Uses simple {variable_name} placeholders. Unknown variables are left as-is."""
    result = template
    for key, value in variables.items():
        result = result.replace("{" + key + "}", str(value))
    return result
