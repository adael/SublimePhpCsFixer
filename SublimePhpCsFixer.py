import sublime
import sublime_plugin
import os
import tempfile
import subprocess
import re
import json


def load_settings():
    return sublime.load_settings("SublimePhpCsFixer.sublime-settings")


def setting_enabled(name):
    return load_settings().get(name)


def is_windows():
    return sublime.platform() == "windows"


def is_executable_file(file_path):
    return os.path.isfile(file_path) and os.access(file_path, os.X_OK)


def is_readable_file(file_path):
    return os.path.isfile(file_path) and os.access(file_path, os.R_OK)


def which(program):
    """Code from: https://stackoverflow.com/a/377028/584639"""
    fpath, fname = os.path.split(program)
    if fpath:
        if is_executable_file(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_executable_file(exe_file):
                return exe_file

    return None


def fixer_possible_paths():
    paths = []

    if is_windows():
        executable_name = "php-cs-fixer.bat"
    else:
        executable_name = "php-cs-fixer"

    project_data = sublime.active_window().project_data()
    if project_data:
        project_path = project_data['folders'][0]['path']
        paths.append(os.path.join(project_path, "vendor", "bin", executable_name))

    if "COMPOSER_HOME" in os.environ:
        paths.append(os.path.join(
            os.environ["COMPOSER_HOME"], "vendor", "bin", executable_name))

    if "APPDATA" in os.environ:
        paths.append(os.path.join(
            os.environ["APPDATA"], "composer", "bin", executable_name))

    if "HOME" in os.environ:
        paths.append(os.path.join(
            os.environ["HOME"],
            ".composer",
            "vendor",
            "bin",
            executable_name))

        paths.append(os.path.join(
            os.environ["HOME"],
            ".config",
            "composer",
            "vendor",
            "bin",
            executable_name))

    paths.append(which(executable_name))

    return paths


def create_process_for_platform(cmd):
    if is_windows():
        # We need to hide the console window
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        si = None

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        startupinfo=si)


def get_project_folder(file):

    project_data = sublime.active_window().project_data()

    if not project_data:
        return None

    project_folders = project_data.get('folders', [])
    project_paths = (p['path'] for p in project_folders)
    for path in project_paths:
        if file.startswith(path):
            return path

    return None


class Logger:
    def __init__(self, settings):
        self.settings = settings

    def console(self, msg):
        print("PHP CS Fixer: {0}".format(msg))

    def debug(self, msg):
        if self.settings.get("debug"):
            print("PHP CS Fixer (DEBUG): {0}".format(msg))


class FormatterSettings:
    def __init__(self, settings):
        self.settings = settings
        self.variables = self.get_active_window_variables()

    def get(self, key):
        return self.settings.get(key)

    def get_expanded(self, key):
        return self.expand(self.settings.get(key))

    def expand(self, value):
        return sublime.expand_variables(value, self.variables)

    def get_active_window_variables(self):
        variables = sublime.active_window().extract_variables()

        if 'file' in variables:
            folder = get_project_folder(variables['file'])
            if folder:
                variables['folder'] = folder

        return variables


class FixerProcess:
    def __init__(self, settings: FormatterSettings, logger: Logger):
        self.logger = logger
        self.settings = settings

    def run(self, tmp_file):
        cmd = self.create_cmd(tmp_file)
        self.logger.debug("Using cmd:")
        self.logger.debug(cmd)

        p = create_process_for_platform(cmd)
        output, err = p.communicate()

        if p.returncode != 0:
            self.logger.console("There was an error formatting the view")
            self.logger.console("Command: {0}".format(cmd))
            self.logger.console("Error output: {0}".format(err))

    def create_cmd(self, tmp_file):
        config = self.config_param()
        rules = self.rules_param()
        allow_risky = self.allow_risky_param()

        if rules and config:
            self.logger.console("rules and config are both present, rules prevails")
            config = None

        return list(filter(None, [
            self.settings.get_expanded('php_path'),
            self.get_configured_php_cs_fixer_path(),
            "fix",
            rules,
            config,
            allow_risky,
            "--using-cache=no",
            tmp_file,
        ]))

    def config_param(self):
        configs = self.settings.get("config")

        if not configs:
            return None

        if not type(configs) is list:
            configs = [configs]

        for config in configs:
            config_path = self.settings.expand(config)
            self.logger.debug("Looking for config: " + config_path)
            if is_readable_file(config_path):
                self.logger.console("Using config: " + config_path)
                return '--config=' + config_path

        self.logger.debug("Not using config")

        return None

    def rules_param(self):
        rules = self.settings.get('rules')

        if not rules:
            return None

        if isinstance(rules, list):
            rules = ",".join(rules)

        if isinstance(rules, dict):
            rules = json.dumps(rules)

        if isinstance(rules, str):
            self.logger.console("Using rules: " + rules)
            return "--rules=" + rules

        return None

    def allow_risky_param(self):
        if self.settings.get("allow_risky"):
            return "--allow-risky=yes"
        
        return None

    def get_configured_php_cs_fixer_path(self):
        path = self.settings.get_expanded('path')

        if not path:
            path = self.locate_php_cs_fixer()

        if not path:
            raise ExecutableNotFoundException("Couldn't find php-cs-fixer")

        if not is_executable_file(path):
            raise ExecutableNotFoundException(
                "Couldn't execute file: {0}".format(path))

        return path

    def locate_php_cs_fixer(self):
        paths = fixer_possible_paths()
        for path in paths:
            self.logger.debug("looking for php-cs-fixer at: " + path)
            if is_executable_file(path):
                self.logger.console("autodetected: " + path)
                return path

        self.logger.console("php-cs-fixer file not found")


class ViewFormatter:

    def __init__(self, settings: FormatterSettings, logger):
        self.settings = settings
        self.logger = logger

    def format(self, contents):
        self.logger.console("Formatting view...")
        return self.format_contents(contents)

    def format_contents(self, contents):
        """
        Write the contents in a temporary file, format it with php-cs-fixer and returns the formatted contents.

        For supporting ST2 and ST3, I do use the following, because it's compatible in python 2/3 and seems
        to work properly.

            - file.write(contents.encode(encoding))
            - file.read().decode(encoding)

        :param contents:
        :return:
        """
        fd, tmp_file = tempfile.mkstemp()

        encoding = self.settings.get("encoding")

        with open(tmp_file, 'wb') as file:
            file.write(contents.encode(encoding))
            file.close()

        try:
            self.format_file(tmp_file)
            with open(tmp_file, 'rb') as file:
                content = file.read().decode(encoding)
                file.close()
        finally:
            os.close(fd)
            os.remove(tmp_file)

        return content

    def format_file(self, tmp_file):
        fixer = FixerProcess(self.settings, self.logger)
        fixer.run(tmp_file)


class SublimePhpCsFixCommand(sublime_plugin.TextCommand):

    def __init__(self, view):
        sublime_plugin.TextCommand.__init__(self, view)
        self.settings = load_settings()
        self.logger = Logger(self.settings)

    def is_enabled(self):
        return self.is_supported_scope()

    def run(self, edit):
        try:
            self.format(edit)
        except ExecutableNotFoundException as e:
            self.logger.console(str(e))

    def format(self, edit):
        region = sublime.Region(0, self.view.size())
        contents = self.view.substr(region)

        if not contents:
            self.logger.console("Done. No contents")
            return

        formatter = ViewFormatter(
            FormatterSettings(self.settings), self.logger)
        new_contents = formatter.format(contents)

        if new_contents and new_contents != contents:
            self.view.replace(edit, region, new_contents)
            self.logger.console("Done. View formatted")
        else:
            self.logger.console("Done. No changes")

    def is_supported_scope(self):
        scopes = self.view.scope_name(self.view.sel()[0].begin())
        return 'embedding.php' in scopes and not self.is_excluded()

    def is_excluded(self):
        if not self.settings.has('exclude'):
            return False

        exclude = self.settings.get('exclude')
        file_name = self.view.file_name()

        if not type(exclude) is list:
            exclude = [exclude]

        for pattern in exclude:
            if re.match(pattern, file_name) is not None:
                self.logger.console(
                    file_name + ' is excluded via pattern: ' + pattern)
                return True

        return False


class SublimePhpCsFixListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        if setting_enabled('on_save'):
            view.run_command('sublime_php_cs_fix')

    def on_load(self, view):
        if setting_enabled('on_load'):
            view.run_command('sublime_php_cs_fix')


class ExecutableNotFoundException(BaseException):
    pass
