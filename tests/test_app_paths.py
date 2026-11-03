"""Runtime path behaviour for source and frozen (PyInstaller) builds."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ledger import app as app_module


class DefaultDatabasePathTests(unittest.TestCase):
    def test_source_mode_uses_project_data_directory(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOCALAPPDATA", None)
            self.assertEqual(
                app_module._default_db(),
                Path(app_module.__file__).resolve().parent.parent / "data" / "ledger.db",
            )

    def test_frozen_mode_uses_local_appdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "frozen", True, create=True):
                with mock.patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                    self.assertEqual(
                        app_module._default_db(),
                        Path(tmp) / "ZhaoZhaoRecord" / "data" / "ledger.db",
                    )

    def test_frozen_mode_without_localappdata(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("LOCALAPPDATA", None)
                self.assertEqual(
                    app_module._default_db(),
                    Path.home() / "AppData" / "Local" / "ZhaoZhaoRecord" / "data" / "ledger.db",
                )


if __name__ == "__main__":
    unittest.main()
