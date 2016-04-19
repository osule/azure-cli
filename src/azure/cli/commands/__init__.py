from __future__ import print_function
import sys
import time
from importlib import import_module
from collections import defaultdict, OrderedDict
from pip import get_installed_distributions

# Find our command modules, they start with 'azure-cli-'
INSTALLED_COMMAND_MODULES = [dist.key.replace('azure-cli-', '')
                             for dist in get_installed_distributions(local_only=True)
                             if dist.key.startswith('azure-cli-')]

COMMON_PARAMETERS = {
    'resource_group_name': {
        'name': '--resourcegroup -g',
        'metavar': 'RESOURCE GROUP',
        'help': 'Name of resource group',
        'required': True
    },
    'location': {
        'name': '--location -l',
        'metavar': 'LOCATION',
        'help': 'Location',
        'required': True
    }
}

class LongRunningOperation(object): #pylint: disable=too-few-public-methods

    progress_file = sys.stderr

    def __init__(self, start_msg='', finish_msg='', poll_interval_ms=1000.0):
        self.start_msg = start_msg
        self.finish_msg = finish_msg
        self.poll_interval_ms = poll_interval_ms

    def __call__(self, poller):
        print(self.start_msg, file=self.progress_file)
        succeeded = False
        try:
            while not poller.done():
                if self.progress_file:
                    print('.', end='', file=self.progress_file)
                    self.progress_file.flush()
                time.sleep(self.poll_interval_ms / 1000.0)
            result = poller.result()
            succeeded = True
            return result
        finally:
            # Ensure that we get a newline after the dots...
            if self.progress_file:
                print(file=self.progress_file)
                print(self.finish_msg if succeeded else '', file=self.progress_file)

class CommandTable(defaultdict):
    """A command table is a dictionary of func -> {name,
                                                   func,
                                                   **kwargs}
    objects.

    The `name` is the space separated name - i.e. 'az vm list'
    `func` represents the handler for the method, and will be called with the parsed
    args from argparse.ArgumentParser. The remaining keyword arguments will be passed to
    ArgumentParser.add_parser.
    """
    def __init__(self):
        super(CommandTable, self).__init__(lambda: {'arguments': []})

    def command(self, name, **kwargs):
        def wrapper(func):
            self[func]['name'] = name
            self[func].update(kwargs)
            return func
        return wrapper

    def description(self, description):
        def wrapper(func):
            self[func]['description'] = description
            return func
        return wrapper

    def help(self, help_file):
        def wrapper(func):
            self[func]['help_file'] = help_file
            return func
        return wrapper

    def option(self, name, **kwargs):
        def wrapper(func):
            opt = dict(kwargs)
            opt['name'] = name
            self[func]['arguments'].append(opt)
            return func
        return wrapper

def _get_command_table(module_name):
    module = import_module('azure.cli.command_modules.' + module_name)
    return module.command_table

def get_command_table(module_name=None):
    '''Loads command table(s)

    When `module_name` is specified, only commands from that module will be loaded.
    If the module is not found, all commands are loaded.
    '''
    loaded = False
    if module_name:
        try:
            command_table = _get_command_table(module_name)
            loaded = True
        except ImportError:
            # Unknown command - we'll load all installed modules below
            pass

    if not loaded:
        command_table = {}
        for mod in INSTALLED_COMMAND_MODULES:
            command_table.update(_get_command_table(mod))

    ordered_commands = OrderedDict(sorted(command_table.items(), key=lambda item: item[1]['name']))
    return ordered_commands
