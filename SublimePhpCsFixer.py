import sublime, sublime_plugin
import os, tempfile, subprocess
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


def locate_php_cs_fixer():
    project_path = sublime.active_window().project_data()['folders'][0]['path']
    path = os.path.join(project_path, "vendor/bin/php-cs-fixer")
    if is_executable_file(path):
        log_to_console("uses local installation")
        return path

    if is_windows():
        paths = locate_in_windows()
    else:
        paths = locate_in_linux()

    for path in paths:
        if is_executable_file(path):
            log_to_console("autodetected: " + path)
            return path

    log_to_console("php-cs-fixer file not found")


def locate_in_windows():
    """return possible paths for php-cs-fixer on Windows"""
    paths = []

    if "COMPOSER_HOME" in os.environ:
        paths.append(os.environ["COMPOSER_HOME"] + "\\vendor\\bin\\php-cs-fixer.bat")

    if "APPDATA" in os.environ:
        paths.append(os.environ["APPDATA"] + "\\composer\\vendor\\bin\\php-cs-fixer.bat")

    paths.append(which("php-cs-fixer.bat"))

    return paths


def locate_in_linux():
    """return possible paths for php-cs-fixer on Linux and Mac"""
    paths = []

    if "COMPOSER_HOME" in os.environ:
        paths.append(os.environ["COMPOSER_HOME"] + "/vendor/bin/php-cs-fixer")

    if "HOME" in os.environ:
        paths.append(os.environ["HOME"] + "/.composer/vendor/bin/php-cs-fixer")
        paths.append(os.environ["HOME"] + "/.config/composer/vendor/bin/php-cs-fixer")

    paths.append(which("php-cs-fixer"))

    return paths


def log_to_console(msg):
    print("PHP CS Fixer: {0}".format(msg))


def format_contents(contents, settings):
    """
    Write the contents in a temporary file, format it with php-cs-fixer and return the formatted contents.

    For supporting ST2 and ST3, I do use the following, because it's compatible in python 2/3 and seems
    to work properly.

        - file.write(contents.encode(encoding))
        - file.read().decode(encoding)

    :param contents:
    :return:
    """
    fd, tmp_file = tempfile.mkstemp()

    encoding = "utf8"

    with open(tmp_file, 'wb') as file:
        file.write(contents.encode(encoding))
        file.close()

    try:
        format_file(tmp_file, settings)
        with open(tmp_file, 'rb') as file:
            content = file.read().decode(encoding)
            file.close()
    finally:
        os.close(fd)
        os.remove(tmp_file)

    return content


def format_file(tmp_file, settings):
    php_path = settings.get('php_path')
    path = settings.get('path')

    if not path:
        path = locate_php_cs_fixer()

    if not path:
        raise ExecutableNotFoundException("Couldn't find php-cs-fixer")
    if not is_executable_file(path):
        raise ExecutableNotFoundException("Couldn't execute file: {0}".format(path))

    configs = settings.get('config')
    rules = settings.get('rules')

    cmd = [php_path] if php_path else []
    cmd += [path, "fix", "--using-cache=no", tmp_file]

    if configs:
        if not type(configs) is list:
            configs = [configs]

        variables = get_active_window_variables()

        for config in configs:
            config_path = sublime.expand_variables(config, variables)
            if is_readable_file(config_path):
                cmd.append('--config=' + config_path)
                log_to_console("Using config: " + config_path)
                break;

    if rules:
        if isinstance(rules, list):
            rules = ",".join(rules)

        if isinstance(rules, dict):
            rules = json.dumps(rules)

        if isinstance(rules, str):
            cmd.append("--rules=" + rules)
            log_to_console("Using rules: " + rules)

    p = create_process_for_platform(cmd)
    output, err = p.communicate()

    if p.returncode != 0:
        log_to_console("There was an error formatting the view")
        log_to_console("Command: {0}".format(cmd))
        log_to_console("Error output: {0}".format(err))


def get_active_window_variables():
    variables = sublime.active_window().extract_variables()

    if 'file' in variables:
        folder = get_project_folder(variables['file'])
        if folder:
            variables['folder'] = folder

    return variables


def create_process_for_platform(cmd):
    if is_windows():
        # We need to hide the console window
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        si = None

    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, startupinfo=si)


def get_project_folder(file):

    project_data = sublime.active_window().project_data();

    if not project_data:
        return None

    project_folders = project_data.get('folders', [])
    project_paths = (p['path'] for p in project_folders)
    for path in project_paths:
        if file.startswith(path):
            return path

    return None


class SublimePhpCsFixCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        sublime_plugin.TextCommand.__init__(self, view)
        self.settings = load_settings()

    def is_enabled(self):
        return self.is_supported_scope(self.view)

    def run(self, edit):
        try:
            log_to_console("Formatting view...")
            region = sublime.Region(0, self.view.size())
            contents = self.view.substr(region)

            if contents:
                formatted = format_contents(contents, self.settings)
                if formatted and formatted != contents:
                    self.view.replace(edit, region, formatted)
                    log_to_console("Done. View formatted")
                else:
                    log_to_console("Done. No changes")
            else:
                log_to_console("Done. No contents")
        except ExecutableNotFoundException as e:
            log_to_console(str(e))

    def is_supported_scope(self, view):
        return 'embedding.php' in view.scope_name(view.sel()[0].begin()) and not self.is_excluded(view)

    def is_excluded(self, view):
        if not self.settings.has('exclude'):
            return False

        exclude = self.settings.get('exclude')
        file_name = view.file_name()

        if not type(exclude) is list:
            exclude = [exclude]

        for pattern in exclude:
            if re.match(pattern, file_name) is not None:
                log_to_console(file_name + ' is excluded via pattern: ' + pattern)
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
