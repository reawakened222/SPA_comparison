import ntpath

def is_testware_translation_unit(compile_command_entry):
    return ("test" in str(compile_command_entry["directory"]).lower() or 
            "test" in str(compile_command_entry["file"]).lower())

def is_testcase_translation_unit_coarse(compile_command_entry):
    dir, name = ntpath.split(str(compile_command_entry["file"]))
    return "test" in name.lower()

def is_testcase_translation_unit_finegrained(compile_command_entry):
    test_strings = ["assert", "equals", "test", "unit"]
    with open(str(compile_command_entry["file"]), "r") as content:
        content_lowercase = content.read()
        for ts in test_strings:
            if ts in content_lowercase:
                return True
    return False