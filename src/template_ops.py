def remove_signature_template(config, template_id):
    """Remove a template safely and preserve a valid active template selection."""
    templates = config.get_signature_templates()
    if not any(t.get("id") == template_id for t in templates):
        return False

    if len(templates) <= 1:
        return False

    config.delete_template(template_id)

    if config.get_active_template_id() == template_id:
        remaining_templates = config.get_signature_templates()
        if remaining_templates:
            config.set_active_template_id(remaining_templates[0].get("id"))

    return True
