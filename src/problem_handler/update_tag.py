import src.helper as helper

# The keys of tioj_instance.auto_parse that hold the two tag lists.
TAG_ATTRIBUTES = {
    False: 'tag_list',
    True: 'solution_tag_list',
}

'''
Requirement: None.

Description: Split a TIOJ tag list into its tags. TIOJ keeps both tag lists as one comma
             separated string, so this is also how the tags given on the command line are read,
             which lets "a,b" and "a b" mean the same thing.

Return value: The list of tags, in the order they were written, without duplicates or blanks.
'''
def parse_tags(values):
    tags = []
    for value in values:
        for tag in str(value).split(','):
            tag = tag.strip()
            if tag and tag not in tags:
                tags.append(tag)
    return tags

'''
Requirement: Admin permission.

Description: Add, remove or replace the tags of a TIOJ problem. The current tags are read back
             from the edit form first, so that adding a tag keeps the ones that are already
             there instead of overwriting them.

             - tags only: the tags are appended to the existing ones;
             - remove: the given tags are dropped, the rest are kept;
             - clear: every existing tag is dropped first, so clear with tags replaces the list
               and clear on its own empties it.

Return value: None.
'''
def update_tag(problem_id, tags, tioj, settings, remove=False, clear=False, solution=False):
    if not str(problem_id).isdigit():
        helper.throw_error('problem_id must be digits')
    problem_id = str(int(problem_id))

    attribute = TAG_ATTRIBUTES[bool(solution)]
    if attribute not in settings.tioj_instance.auto_parse.__dict__['_box_config']['__safe_keys']:
        helper.throw_error(f'Cannot find attribute {attribute} in tioj_instance_settings.toml/tioj_instance.auto_parse.')
    field = eval(f'settings.tioj_instance.auto_parse.{attribute}')

    helper.throw_status(f'Updating the {attribute} of TIOJ problem {problem_id}...')

    form_data, _ = tioj.get_form(settings.endpoints.edit_problem % problem_id)
    if field not in form_data:
        helper.throw_error(f'Cannot find the field {field} on the edit form of TIOJ problem {problem_id}.')
    current = parse_tags([form_data[field]])
    helper.throw_status(f'Current {attribute}: {", ".join(current) if current else "(empty)"}')

    tags = parse_tags(tags)

    if remove:
        missing = [tag for tag in tags if tag not in current]
        if missing:
            helper.throw_warning(f'Not tagged with {", ".join(missing)}, nothing to remove there.')
        result = [tag for tag in current if tag not in tags]
    else:
        result = [] if clear else list(current)
        result += [tag for tag in tags if tag not in result]

    if result == current:
        helper.throw_info(f'The {attribute} of TIOJ problem {problem_id} is already what it should be, nothing to do.')
        return

    response = tioj.submit_form(settings.endpoints.edit_problem % problem_id, data={field: ','.join(result)})

    helper.throw_info(f'Completed update the {attribute} of TIOJ problem {problem_id}: {", ".join(result) if result else "(empty)"}')
