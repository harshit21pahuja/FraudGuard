import unittest
from src.utils.config import get_project_root, load_config
from src.data.validate_datasets import validate_dataset_presence


class TestConfigAndStructure(unittest.TestCase):
    def test_project_root_exists(self):
        root = get_project_root()
        self.assertTrue(root.exists(), f"Project root does not exist: {root}")
        self.assertTrue((root / "configs" / "project_config.yaml").exists(), "Config file missing")

    def test_load_config(self):
        config = load_config()
        self.assertIsInstance(config, dict, "Config should load as a dictionary")
        self.assertIn("project", config)
        self.assertEqual(config["project"]["name"], "FraudGuard")
        self.assertIn("datasets", config)
        self.assertIn("dataset_a", config["datasets"])
        self.assertIn("dataset_b", config["datasets"])
        self.assertIn("models", config)
        self.assertEqual(len(config["models"]), 5)  # 5 required classifiers

    def test_validate_dataset_presence(self):
        report = validate_dataset_presence()
        self.assertIn("dataset_a", report)
        self.assertIn("dataset_b", report)
        self.assertIn("ready", report["dataset_a"])
        self.assertIn("ready", report["dataset_b"])


if __name__ == "__main__":
    unittest.main()

