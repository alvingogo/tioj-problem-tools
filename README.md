# TIOJ Problem Tools
**The project is not well tested. Issues or pull requests are welcome to improve us.**

tioj-problem-tools is a python tool for assisting [TIOJ INFOR Online Judge](https://github.com/TIOJ-INFOR-Online-Judge/tioj) problem setting.

By using a specific format base on [Task Preparation System](https://github.com/ioi-2017/tps), problem setters can obtain a command-line interface to conveniently set up problems and then upload them onto a TIOJ-format online judge.

To be short, tioj-problem-tools parses TPS-format problem directories and uses the front-end interface to interact with TIOJ. To deal with custom TIOJ-format, tioj-problem-tools also provides [toml](https://toml.io/en/) configuration files and [JSON schema](https://json-schema.org/understanding-json-schema/index.html) for users to customize their formats.

## Prerequisites

You may need to install the required python packages.
```
pip install -r requirement.txt
```

## Usage

Tell tioj-problem-tools about your TIOJ instance by adding a profile. It asks for the password
and stores it in your system keyring, so nothing secret is written to a file.
```
python tioj.py profile add local --url http://localhost:4000 --username your_name
```

`configs/default_settings.toml` is tracked by git, so filling your url and password in there
means either committing them or carrying a dirty working tree forever. Profiles are kept out of
the repository instead, which also lets you hold an account on more than one TIOJ.

After then, run the script with python.
```
python tioj.py
```

You can use the `--help` option to get more information about the usage.
```
python tioj.py --help
```

Since this tool is developed by [Typer](https://typer.tiangolo.com/), you can also use [Typer CLI](https://typer.tiangolo.com/typer-cli/) for convenience (like having auto-completion).
```
typer tioj.py
```

## Features

### Prettify command line interface

With the help of [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/en/stable/introduction.html), tioj-problem-tools has a pretty interface. Make users have a comfortable experience.

### Switch between TIOJ instances

Each profile names a url and a username, and owns its password in the system keyring. Switch the
one every command uses with `profile use`, or override it for a single run with `--profile`,
which is accepted both before and after the subcommand.
```
python tioj.py profile list
python tioj.py profile use ck
python tioj.py --profile local whoami
python tioj.py whoami --profile local
```

With no profile at all, the credentials in `configs/default_settings.toml` are used as before.

### JSON verification via JSON schema

tioj-problem-tools use the [python implementation](https://python-jsonschema.readthedocs.io/en/stable/) of [JSON schema](https://json-schema.org/understanding-json-schema/index.html) to set up proper verificatifor the json files in tps directories. Users can also modify the schema to fit their requirements.

### Neat config files

tioj-problem-tools provide [toml](https://toml.io/en/) configuration files to read configurations of itself in the directory `configs/`. Whenever users want to customize their formats, users can always, and only need to, modify the content in `configs/` (including the JSON schema) except changing the attributes' names.

## Current Development Environment

- Operating System: macOS Monterey 12.6
- Language: Python 3.9.6
    - typer-0.7.0
    - rich-12.6.0
    - bs4-4.11.1 
    - html_form_to_dict-2022.10.1
    - dynaconf-3.1.11
    - jsonschema-4.17.3
    - lxml-4.9.2
    - six-1.15.0
    - termcolor-2.1.0
    - requests_toolbelt-1.0.0

## Todolist

- Allow uploading testcases without tps directory format validation.
- Allow "Banned compilers" when editing TIOJ problem's metadata.
- A more comfortable usage for replacing the strings.
- A more comfortable usage of "tag lists".
- Testing.
- Interactive CLI.
