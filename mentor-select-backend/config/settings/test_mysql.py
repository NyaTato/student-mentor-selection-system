"""Opt-in MySQL regression settings. Django owns only a fresh test_smsp_* test DB.

No migration or data repair is performed against the original business database.
Requires SMSP_ALLOW_ISOLATED_MYSQL_TESTS=1 and SMSP_TEST_DATABASE=test_smsp_<unique>.
Credentials remain local environment variables / untracked .env, never in reports.
"""
import os
import re
from copy import deepcopy

from .test import *  # noqa: F403,F401
from .base import DATABASES as _base_databases

_test_name = os.environ.get('SMSP_TEST_DATABASE', '')
if os.environ.get('SMSP_ALLOW_ISOLATED_MYSQL_TESTS') != '1' or not re.fullmatch(r'test_smsp_[a-z0-9_]{8,40}', _test_name):
    raise RuntimeError('Opt in with a unique test_smsp_* database name; business DB testing is forbidden')

_mysql = deepcopy(_base_databases['default'])
_mysql.update({
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'smsp_validation_not_used',
    'HOST': os.environ.get('SMSP_TEST_MYSQL_HOST', '127.0.0.1'),
    'PORT': os.environ.get('SMSP_TEST_MYSQL_PORT', '3306'),
    'CONN_MAX_AGE': 0,
    'TEST': {'NAME': _test_name, 'CHARSET': 'utf8mb4'},
    'OPTIONS': {'charset': 'utf8mb4', 'isolation_level': 'repeatable read'},
})
DATABASES = {'default': _mysql}
