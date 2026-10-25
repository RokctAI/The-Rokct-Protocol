"""A persona marker must never name a registry template.

compose_backend.resolve_composer_config looks up .rokct/config/app_type in the
composer registry and overwrites composer.json when a template matches. The
rCore shell's marker is "tenant", and compose_product.py commits a pinned
composer.json into it, so a composer/tenant.json would silently turn every
composed image into that template.
"""

import os
import unittest

COMPOSER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "composer")
PERSONA_MARKERS = ("tenant",)


class PersonaMarkerNotTemplateTest(unittest.TestCase):
    def test_no_template_named_after_a_persona_marker(self):
        for marker in PERSONA_MARKERS:
            self.assertFalse(os.path.exists(os.path.join(COMPOSER_DIR, marker + ".json")), marker)

    def test_tenant_erp_template_exists(self):
        self.assertTrue(os.path.exists(os.path.join(COMPOSER_DIR, "tenant_erp.json")))


if __name__ == "__main__":
    unittest.main()
