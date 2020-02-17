import logging

from envee.package_managers import Pip
from envee.virtual_environments import VirtualEnv


if __name__ == '__main__':
    # logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)
    venv = VirtualEnv('venv', Pip)
    with venv.load() as env:
        env.install('requests', 'mypy').log()
        env.run(['python', 'test.py']).log()
