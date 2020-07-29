# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import sys
import uuid
import timeit

from knack.completion import ARGCOMPLETE_ENV_NAME
from knack.log import get_logger

from azure.cli.core import AzCli, MainCommandsLoader
from knack.events import EVENT_CLI_PRE_EXECUTE, EVENT_CLI_POST_EXECUTE
from knack.cli import CLI


class CliParser(AzCli):
    def __init__(self, **kwargs):
        super(CliParser, self).__init__(**kwargs)

    def parse(self, args, initial_invocation_data=None, out_file=None):
        """ Invoke a command.

        :param args: The arguments that represent the command
        :type args: list, tuple
        :param initial_invocation_data: Prime the in memory collection of key-value data for this invocation.
        :type initial_invocation_data: dict
        :param out_file: The file to send output to. If not used, we use out_file for knack.cli.CLI instance
        :type out_file: file-like object
        :return: The exit code of the invocation
        :rtype: int
        """
        from knack.util import CommandResultItem

        if not isinstance(args, (list, tuple)):
            raise TypeError('args should be a list or tuple.')
        exit_code = 0
        try:
            if self.enable_color:
                import colorama
                colorama.init()
                if self.out_file == sys.__stdout__:
                    # point out_file to the new sys.stdout which is overwritten by colorama
                    self.out_file = sys.stdout

            args = self.completion.get_completion_args() or args
            out_file = out_file or self.out_file

            self.logging.configure(args)
            logger.debug('Command arguments: %s', args)

            self.raise_event(EVENT_CLI_PRE_EXECUTE)
            if CLI._should_show_version(args):
                self.show_version()
                self.result = CommandResultItem(None)
            else:
                self.invocation = self.invocation_cls(cli_ctx=self,
                                                      parser_cls=self.parser_cls,
                                                      commands_loader_cls=self.commands_loader_cls,
                                                      help_cls=self.help_cls,
                                                      initial_data=initial_invocation_data)
                cmd_result = self.invocation.execute(args)
                self.result = cmd_result
                exit_code = self.result.exit_code
                output_type = self.invocation.data['output']
                if cmd_result and cmd_result.result is not None:
                    formatter = self.output.get_formatter(output_type)
                    self.output.out(cmd_result, formatter=formatter, out_file=out_file)

                print("#####")
                print(self.invocation.expanded_arg, self.invocation.cmd_copy)
        except KeyboardInterrupt as ex:
            exit_code = 1
            self.result = CommandResultItem(None, error=ex, exit_code=exit_code)
        except Exception as ex:  # pylint: disable=broad-except
            exit_code = self.exception_handler(ex)
            self.result = CommandResultItem(None, error=ex, exit_code=exit_code)
        except SystemExit as ex:
            exit_code = ex.code
            self.result = CommandResultItem(None, error=ex, exit_code=exit_code)
            raise ex
        finally:
            self.raise_event(EVENT_CLI_POST_EXECUTE)

            if self.enable_color:
                colorama.deinit()

        return exit_code

from azure.cli.core.commands import AzCliCommandInvoker
class AzCliCommandParseInvoker(AzCliCommandInvoker):
    def _run_job(self, expanded_arg, cmd_copy):
        print("####")
        self.params = self._filter_params(expanded_arg)
        self.expanded_arg = expanded_arg
        self.cmd_copy = cmd_copy
        self.command = cmd_copy.loader.command_table[cmd_copy.name]
        self.operations_tmpl = self.command.command_kwargs["operations_tmpl"]
        try:
            self.params.update({"XXX": 2})
            cmd_copy(self.params)
        except Exception as e:
            import traceback
            pass
            self.function_name = e.args[0].split("()")[0]
        pass

    def __call__(self, *args, **kwargs):
        return self.handler(*args, **kwargs)

def get_default_cli():
    from azure.cli.core.azlogging import AzCliLogging
    from azure.cli.core.parser import AzCliCommandParser
    from azure.cli.core._config import GLOBAL_CONFIG_DIR, ENV_VAR_PREFIX
    from azure.cli.core._help import AzCliHelp
    from azure.cli.core._output import AzOutputProducer

    return CliParser(
        cli_name='az',
        config_dir=GLOBAL_CONFIG_DIR,
        config_env_var_prefix=ENV_VAR_PREFIX,
        commands_loader_cls=MainCommandsLoader,
        invocation_cls=AzCliCommandParseInvoker,
        parser_cls=AzCliCommandParser,
        logging_cls=AzCliLogging,
        output_cls=AzOutputProducer,
        help_cls=AzCliHelp)


import azure.cli.core.telemetry as telemetry


# A workaround for https://bugs.python.org/issue32502 (https://github.com/Azure/azure-cli/issues/5184)
# If uuid1 raises ValueError, use uuid4 instead.
try:
    uuid.uuid1()
except ValueError:
    uuid.uuid1 = uuid.uuid4


logger = get_logger(__name__)


def cli_main(cli, args):
    return cli.parse(args)


if __name__ == "__main__":

    az_cli = get_default_cli()

    try:
        start_time = timeit.default_timer()

        exit_code = cli_main(az_cli, sys.argv[1:])

        elapsed_time = timeit.default_timer() - start_time

        sys.exit(exit_code)

    except KeyboardInterrupt:
        sys.exit(1)
    except SystemExit as ex:  # some code directly call sys.exit, this is to make sure command metadata is logged
        exit_code = ex.code if ex.code is not None else 1

        try:
            elapsed_time = timeit.default_timer() - start_time
        except NameError:
            pass

        raise ex
    finally:
        try:
            logger.info("command ran in %.3f seconds.", elapsed_time)
        except NameError:
            pass
