import os

import src.env as env
import src.helper as helper
from src.config import settings
from src.config import keyring_service

profiles_filename = 'profiles.json'

# The alias given by --profile on the command line, which overrides the current profile for this
# run only. tioj.py sets it before handing over to typer.
cli_override = None

'''
Requirement: None.

Description: Remember the profile alias --profile asked for. Keeping it here rather than passing
             it down through every command means a command never has to know that profiles
             exist at all.

Return value: None.
'''
def set_cli_override(alias):
    global cli_override
    cli_override = alias

'''
Requirement: None.

Description: Locate the profiles file. It is looked up next to the other configs first, so that
             the CONFIGS_DIR environment variable keeps working, and then in the XDG config
             directory. A new file is created in the XDG directory, which lives outside the
             repository and therefore cannot be committed by accident.

Return value: The path to the profiles file, or None when for_write is False and none exists.
'''
def profiles_path(for_write=False):
    candidates = [os.path.join(env.CONFIGS_DIR, profiles_filename), xdg_profiles_path()]

    for path in candidates:
        if os.path.isfile(path):
            return path

    return xdg_profiles_path() if for_write else None

def xdg_profiles_path():
    config_home = os.environ.get('XDG_CONFIG_HOME')
    if not config_home:
        config_home = os.path.join(os.path.expanduser('~'), '.config')
    return os.path.join(config_home, 'tioj-problem-tools', profiles_filename)

'''
Requirement: None.

Description: Read the profiles file, tolerating its absence.

Return value: A dict with the keys 'current' and 'profiles'.
'''
def load_profiles():
    path = profiles_path()
    if path is None:
        return {'current': None, 'profiles': {}}

    data = helper.read_json(path)
    data.setdefault('current', None)
    data.setdefault('profiles', {})
    return data

'''
Requirement: None.

Description: Write the profiles file, creating its directory when needed.

Return value: The path that was written.
'''
def save_profiles(data):
    path = profiles_path(for_write=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    helper.write_json(path, data)
    return path

'''
Requirement: None.

Description: Decide which TIOJ instance and account to use. An alias given on the command line
             wins, then the 'current' profile, and finally default_settings.toml so that the
             tool still works without any profile at all.

Return value: The tuple (alias, tioj_url, tioj_username), where alias is None when the values
              came from default_settings.toml.
'''
def resolve(alias=None):
    data = load_profiles()

    if alias is None:
        alias = cli_override
    if alias is None:
        alias = data['current']

    if alias is None:
        return None, settings.default.tioj_url, settings.default.tioj_username

    if alias not in data['profiles']:
        known = ', '.join(sorted(data['profiles'])) if data['profiles'] else '(none)'
        helper.throw_error(f'Unknown profile [bold]{alias}[/bold]. Known profiles: {known}.')

    entry = data['profiles'][alias]
    return alias, entry['tioj_url'], entry['tioj_username']

'''
Requirement: None.

Description: Read the password of a profile from the system keyring, which is keyed by the
             alias rather than the username, since the same username may have different
             passwords on different TIOJ instances. Without a profile the password can only
             come from default_settings.toml.

Return value: The password, or an empty string when there is none, which makes
              TIOJ_Session.login prompt for it.
'''
def get_password(alias):
    if alias is None:
        return settings.default.tioj_password

    try:
        import keyring
    except ImportError:
        helper.throw_warning('The python package "keyring" is not installed, cannot read the stored password.')
        return ''

    try:
        password = keyring.get_password(keyring_service, alias)
    except Exception as err:
        helper.throw_warning(f'Cannot read the keyring ({type(err).__name__}): {err}')
        return ''

    if password is None:
        helper.throw_warning(f'No stored password for the profile [bold]{alias}[/bold], run "tioj.py profile add {alias}" to store one.')
        return ''

    return password

'''
Requirement: None.

Description: Store the password of a profile in the system keyring.

Return value: True on success.
'''
def set_password(alias, password):
    try:
        import keyring
        keyring.set_password(keyring_service, alias, password)
    except ImportError:
        helper.throw_error('The python package "keyring" is not installed, cannot store the password.')
    except Exception as err:
        helper.throw_error(f'Cannot write to the keyring ({type(err).__name__}): {err}')
    return True

'''
Requirement: None.

Description: Remove the stored password of a profile, tolerating its absence.

Return value: True when an entry was actually removed.
'''
def delete_password(alias):
    try:
        import keyring
        keyring.delete_password(keyring_service, alias)
    except Exception:
        return False
    return True

'''
Requirement: None.

Description: Report whether a profile has a password stored in the keyring.

Return value: True, False, or None when the keyring itself cannot be reached.
'''
def has_password(alias):
    try:
        import keyring
        return keyring.get_password(keyring_service, alias) is not None
    except Exception:
        return None
