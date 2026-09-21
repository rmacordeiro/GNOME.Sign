from copy import deepcopy

from template_ops import remove_signature_template


class FakeConfig:
    def __init__(self, templates, active_template_id):
        self._templates = deepcopy(templates)
        self._active_template_id = active_template_id

    def get_signature_templates(self):
        return self._templates

    def delete_template(self, template_id):
        self._templates = [t for t in self._templates if t.get("id") != template_id]

    def get_active_template_id(self):
        return self._active_template_id

    def set_active_template_id(self, template_id):
        self._active_template_id = template_id


def test_delete_non_active_template():
    cfg = FakeConfig(
        templates=[{"id": "a"}, {"id": "b"}, {"id": "c"}],
        active_template_id="a",
    )

    removed = remove_signature_template(cfg, "b")

    assert removed is True
    assert [t["id"] for t in cfg.get_signature_templates()] == ["a", "c"]
    assert cfg.get_active_template_id() == "a"


def test_delete_active_template_sets_remaining_as_active():
    cfg = FakeConfig(
        templates=[{"id": "a"}, {"id": "b"}, {"id": "c"}],
        active_template_id="b",
    )

    removed = remove_signature_template(cfg, "b")

    assert removed is True
    assert [t["id"] for t in cfg.get_signature_templates()] == ["a", "c"]
    assert cfg.get_active_template_id() == "a"


def test_refuse_delete_when_last_template():
    cfg = FakeConfig(
        templates=[{"id": "only"}],
        active_template_id="only",
    )

    removed = remove_signature_template(cfg, "only")

    assert removed is False
    assert [t["id"] for t in cfg.get_signature_templates()] == ["only"]
    assert cfg.get_active_template_id() == "only"


def test_delete_unknown_template_id_is_safe():
    cfg = FakeConfig(
        templates=[{"id": "a"}, {"id": "b"}],
        active_template_id="a",
    )

    removed = remove_signature_template(cfg, "unknown")

    assert removed is False
    assert [t["id"] for t in cfg.get_signature_templates()] == ["a", "b"]
    assert cfg.get_active_template_id() == "a"
