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

You must setup your TIOJ url, username and the password in `configs/default_settings.toml` first.

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

### JSON verification via JSON schema

tioj-problem-tools use the [python implementation](https://python-jsonschema.readthedocs.io/en/stable/) of [JSON schema](https://json-schema.org/understanding-json-schema/index.html) to set up proper verificatifor the json files in tps directories. Users can also modify the schema to fit their requirements.

### Neat config files

tioj-problem-tools provide [toml](https://toml.io/en/) configuration files to read configurations of itself in the directory `configs/`. Whenever users want to customize their formats, users can always, and only need to, modify the content in `configs/` (including the JSON schema) except changing the attributes' names.

### Edit the tags without knowing what is already there

`upload-problem` writes the whole `tag_list` from `problem.json`, which makes it awkward to
touch one tag on a problem that is tagged on TIOJ but not in its directory. `update-tag` reads
the current tags back first and edits them in place, so adding one keeps the rest.
```
python tioj.py update-tag 1234 dp graph      # add two tags
python tioj.py update-tag 1234 dp --remove   # drop one
python tioj.py update-tag 1234 dp --clear    # replace everything with dp
python tioj.py update-tag 1234 --clear       # no tags at all
```
Pass `--solution` to edit the solution tags instead. A single argument may hold several tags
separated by commas, the way TIOJ itself stores them.

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
- Testing.
- Interactive CLI.
