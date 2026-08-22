from rich import print
import json
import os
from pathlib import Path

import src.env as env

def throw_info(msg):
    print('[bold green]Info: [/bold green]' + msg)

def throw_status(msg):
    print('[blue]Status: [/blue]' + msg)

def throw_warning(msg):
    print('[bold dark_orange]Warning: [/bold dark_orange]' + msg)

def throw_error(msg, exit_code=1):
    print('[bold red]Error: [/bold red]' + msg)
    exit(exit_code)

def expand_settings_variable(var):
    var = var.replace('{SCRIPT_DIR}', env.SCRIPT_DIR)
    var = var.replace('{CONFIGS_DIR}', env.CONFIGS_DIR)
    return var

def read_file(path):
    path = expand_settings_variable(path)
    try:
        content = Path(path).read_text()
    except FileNotFoundError as err:
        throw_error(f'({path}) ' + str(err))
    except Exception as err:
        throw_error(f'Unexpected error ({type(err).__name__}) while opening {path}: ' + str(err))
    return content 

def read_json(path):
    path = expand_settings_variable(path) 
    with open(path) as json_file:
        try:
            res = json.load(json_file)
        except FileNotFoundError as err:
            throw_error(f'({path}) ' + str(err))
        except ValueError as err:
            throw_error(f'({path}) ' + str(err))
        except Exception as err:
            throw_error(f'Unexpected error ({type(err).__name__}) while opening {path}: ' + str(err))
    return res

def write_json(path, data):
    path = expand_settings_variable(path) 
    with open(path, 'w') as json_file:
        json.dump(data, json_file)

'''
Requirement: None.

Description: Format a list of testdata ids the way TIOJ writes a td_list, where a run of
             consecutive ids is collapsed into 'first-last'. ['1', '2', '3', '4', '6'] becomes
             '1-4,6'. The ids are sorted and deduplicated, since a range only makes sense on
             sorted input. A list holding anything that is not a plain number is joined as it
             is, rather than guessing at its meaning.

Return value: The comma separated string.
'''
def compress_id_list(ids):
    ids = list(ids)
    if not ids:
        return ''
    if not all(str(i).strip().isdigit() for i in ids):
        return ','.join(str(i) for i in ids)

    numbers = sorted(set(int(i) for i in ids))

    groups = []
    first = last = numbers[0]
    for number in numbers[1:]:
        if number == last + 1:
            last = number
        else:
            groups.append((first, last))
            first = last = number
    groups.append((first, last))

    return ','.join(str(first) if first == last else f'{first}-{last}' for first, last in groups)

def replace_header(content, settings):
    for header in settings.default.replace_headers:
        path = expand_settings_variable(settings.default.replace_header_paths)
        content = content.replace(f'#include "{header}"', read_file(os.path.join(path, header)))
    return content
