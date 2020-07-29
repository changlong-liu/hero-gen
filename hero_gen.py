
from cli_parser import get_default_cli

import os
import glob
import shutil
import json

PATH_SETUP_TEMPL = './setup_tmpl'
PATH_TMPL = './gen_tmpl'
PATH_GENERATED = './output'
PATH_GENERATED = 'C:\\ZZ\\projects\\codegen\\azure-cli-extensions\\src\\hero'
hero_name = 'hero'
gen_folder = os.path.join(PATH_GENERATED, "azext_{}".format(hero_name))


def replace_in_file(file_path, pattern, replacement):
    # Read in the file
    with open(file_path, 'r') as file:
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace(pattern, replacement)

    # Write the file out again
    with open(file_path, 'w') as file:
        file.write(filedata)


def gen_extension():

    os.makedirs(gen_folder, exist_ok=True)
    for filename in glob.glob(os.path.join(PATH_TMPL, '*.*')):
        shutil.copy(filename, gen_folder)
        replace_in_file(os.path.join(gen_folder, os.path.basename(
            filename)), "{hero_name}", hero_name)

    for filename in glob.glob(os.path.join(PATH_SETUP_TEMPL, '*.*')):
        shutil.copy(filename, PATH_GENERATED)
        replace_in_file(os.path.join(PATH_GENERATED, os.path.basename(
            filename)), "{hero_name}", hero_name)



def parse_command(args):
    print("parsing: ", args)
    az_cli = get_default_cli()
    az_cli.parse(args)
    return az_cli.invocation.operations_tmpl, az_cli.invocation.function_name, az_cli.invocation.expanded_arg.cmd.arguments, az_cli.invocation.params, az_cli.invocation.expanded_arg


def to_hero_param_name(subcommand, param_name):
    # TODO: need to handle name conflict among multi subcommands
    return param_name
    # if param_name in set(["resource_group_name", ]):
    #     return param_name
    # underline_rp = subcommand[0].split('#')[0].split(".")[-2]
    # return underline_rp + "_" + param_name


def filter_params(params: dict):
    from azure.cli.core.commands import AzCliCommand
    ret = {}
    for k, v in params.items():
        if isinstance(v, AzCliCommand):
            continue
        if k == 'XXX':
            continue
        ret[k] = v
    return ret


def filter_arguments(arguments: dict):
    from azure.cli.core.commands import AzCliCommand
    ret = {}
    for k, v in arguments.items():
        if k in set(["resource_group_name", "tags"]):
            continue
        ret[k] = v
    return ret


def gen_custom(subcommands):
    file_path = os.path.join(gen_folder, 'custom.py')
    with open(file_path, 'r') as file:
        filedata = file.read()

    parsed_params = parse_params(subcommands)
    
    params_in_signature = sorted([(k, v) for k, v in parsed_params.items()], key=lambda x: not x[1].get("required"))
    
    signature = "\ndef {}_go(cmd".format(hero_name)
    for hero_param_name, c in params_in_signature:
        signature += ", " + hero_param_name
        if not c["required"]:
            if isinstance(c["default"], str):
                signature += "=\"" + str(c["default"]) + "\""
            else:
                signature += "=" + str(c["default"])
    signature += "):"
    filedata += signature
    results = []
    for subcommand in subcommands:
        params_dict = filter_params(subcommand[3])
        params = ["cmd"] + ["{sdk_param_name}={hero_param_name}".format(
            sdk_param_name=k, hero_param_name=to_hero_param_name(subcommand, k)) for k, v in params_dict.items() if v is not None]
        result_variable = "_".join(("result of " + subcommand[4].command).split())
        results.append(result_variable)
        content = """
    from {package} import {func}
    {result_variable} = {func}({params})
""".format(package=subcommand[0].split('#')[0], func=subcommand[1], params=", ".join(params), result_variable=result_variable)
        filedata += content

    filedata += "    return {\n"
    for result in results:
        filedata += "        \"{result}\": {result},\n".format(result=result)
    filedata += "    }"
    
    # Write the file out again
    with open(file_path, 'w') as file:
        file.write(filedata)


def parse_params(subcommands):
    parsed_params = {}
    for subcommand in subcommands:
        params = filter_params(subcommand[3])
        for param_name, argument in subcommand[2].items():
            param_name = to_hero_param_name(subcommand, param_name)
            if params.get(param_name) is None:
                continue
            if param_name in parsed_params:
                if not parsed_params[param_name].get("required"):
                    parsed_params[param_name]["required"] = True
                continue
            parsed_params[param_name] = {
                "help": argument.type.settings["help"],
                "required": argument.type.required_tooling,
                "default": None
            }
    for subcommand in subcommands:
        params_dict = filter_params(subcommand[3])
        for k, v in params_dict.items():
            param_name = to_hero_param_name(subcommand, k)
            if param_name in parsed_params and not parsed_params[param_name].get("required"):
                parsed_params[param_name]["default"] = v
    return parsed_params


def gen_params(subcommands):
    file_path = os.path.join(gen_folder, '_params.py')
    with open(file_path, 'r') as file:
        filedata = file.read()

    parsed_params = parse_params(subcommands)
    parsed_params = filter_arguments(parsed_params)
    for param_name, content in parsed_params.items():
        content = """
        c.argument('{hero_param_name}', CLIArgumentType(help='{help}'), required={required})""".format(hero_param_name=param_name, help=content["help"], required=content["required"])
        filedata += content
    # Write the file out again
    with open(file_path, 'w') as file:
        file.write(filedata)


def main():
    with open('./template.txt') as f:
        content = f.readlines()
    content = [x.strip() for x in content]

    subcommands = []
    for line in content:
        subcommands.append(parse_command(line.split()[1:]))

    gen_extension()
    gen_custom(subcommands)
    gen_params(subcommands)
    print("Done! please check: " + PATH_GENERATED)


if __name__ == "__main__":
    main()
