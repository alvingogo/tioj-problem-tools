from dynaconf import Dynaconf
import os
from enum import Enum

import src.env as env

settings = Dynaconf(
    settings_files=[os.path.join(env.CONFIGS_DIR, 'default_settings.toml'),
                    os.path.join(env.CONFIGS_DIR, 'endpoints_settings.toml'),
                    os.path.join(env.CONFIGS_DIR, 'path_settings.toml'),
                    os.path.join(env.CONFIGS_DIR, 'tioj_instance_settings.toml')])

# The service name under which the profile passwords are stored in the system keyring.
keyring_service = 'tioj-problem-tools'

class Compiler(Enum):
    exec(', '.join(settings.tioj_instance.compiler_list) + " = \"" + "\", \"".join(settings.tioj_instance.compiler_list) + "\"")
