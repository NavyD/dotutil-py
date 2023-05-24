
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

from util import ChezmoiArgs, config_log, elevate_writefile


class ChezmoiArgsTest(TestCase):
    def test_args(self):
        args = ChezmoiArgs(
            'chezmoi --debug diff -v /home/xx/.ssh /home/xx/.config')
        assert args.subcommand() == 'diff'
        assert args.has_debug() is True
        assert args.has_verbose() is True
        assert args.target_paths()
        assert len(args.target_paths()) == 2
        assert Path('/home/xx/.config') in args.target_paths()
        assert Path('/home/xx/.ssh') in args.target_paths()

        args = ChezmoiArgs(
            'chezmoi diff -v')
        assert args.subcommand() == 'diff'
        assert args.has_debug() is False
        assert args.has_verbose() is True
        assert not args.target_paths()

        args = ChezmoiArgs('chezmoi diff -v --debug')
        assert args.subcommand() == 'diff'
        assert args.has_debug() is True
        assert args.has_verbose() is True
        assert not args.target_paths()

        args = ChezmoiArgs('chezmoi diff')
        assert args.subcommand() == 'diff'
        assert args.has_verbose() is False
        assert args.has_debug() is False
        assert not args.target_paths()


class UtilFn(TestCase):
    def test_elevate_writefile(self):
        input = 'test write super'
        with tempfile.TemporaryDirectory() as dir:
            path = Path(dir).joinpath('a.txt')
            assert not path.exists()
            elevate_writefile(str(path), input)
            assert path.is_file()
            assert path.stat().st_uid == 0
            assert path.read_text() == input


if __name__ == '__main__':
    config_log(level=logging.DEBUG)
    unittest.main()