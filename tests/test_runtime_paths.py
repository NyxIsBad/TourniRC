import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_paths


class RuntimePathTests(unittest.TestCase):
    def test_source_resources_are_next_to_module(self):
        self.assertEqual(runtime_paths.resource_root(), Path(runtime_paths.__file__).resolve().parent)

    def test_data_and_logs_ignore_working_directory(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            previous = Path.cwd()
            try:
                os.chdir(directory)
                self.assertEqual(runtime_paths.data_dir(), runtime_paths.application_dir() / 'cfg')
                self.assertEqual(runtime_paths.logs_dir(), runtime_paths.application_dir() / 'logs')
            finally:
                os.chdir(previous)

    def test_frozen_paths_split_resources_from_writable_data(self):
        with tempfile.TemporaryDirectory() as bundle, tempfile.TemporaryDirectory() as install:
            executable = str(Path(install) / 'TourniRC.exe')
            with patch.object(sys, 'frozen', True, create=True), \
                    patch.object(sys, '_MEIPASS', bundle, create=True), \
                    patch.object(sys, 'executable', executable), \
                    patch.dict(os.environ, {}, clear=True):
                self.assertEqual(runtime_paths.resource_root(), Path(bundle))
                self.assertEqual(runtime_paths.data_dir(), Path(install) / 'cfg')
                self.assertEqual(runtime_paths.logs_dir(), Path(install) / 'logs')

    def test_environment_overrides_writable_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {
                'TOURNIRC_DATA_DIR': str(root / 'data'),
                'TOURNIRC_LOG_DIR': str(root / 'diagnostics'),
            }, clear=True):
                self.assertEqual(runtime_paths.data_dir(), (root / 'data').resolve())
                self.assertEqual(runtime_paths.logs_dir(), (root / 'diagnostics').resolve())


if __name__ == '__main__':
    unittest.main()
