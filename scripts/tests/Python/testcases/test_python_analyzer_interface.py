import subprocess
from test import support

class TestPylamaInterfaceClass():

    def test_pylama_existence(self):
        """Degenerate test if pylama can be executed"""
        res = subprocess.run(["pylama", "--version"])
        assert res.returncode == 0

    # tmpdir will force pytest to create a temp directory
    def test_pylama(self, tmpdir):
        print(tmpdir)
        assert 0

