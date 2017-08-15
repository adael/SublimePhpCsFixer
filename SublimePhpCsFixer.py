import sublime, sublime_plugin
import os, tempfile, subprocess


def load_settings():
    return sublime.load_settings("SublimePhpCsFixer.sublime-settings")


def setting_enabled(name):
    return load_settings().get(name)


def is_windows():
    return sublime.platform() == "windows"


def is_file(file_path):
    return os.path.isfile(file_path) and os.access(file_path, os.X_OK)


def which(program):
    """Code from: https://stackoverflow.com/a/377028/584639"""
    fpath, fname = os.path.split(program)
    if fpath:
        if is_file(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_file(exe_file):
                return exe_file
    
    return None


def locate_php_cs_fixer():
    if is_windows():
        paths = locate_in_windows()
    else:
        paths = locate_in_linux()
    
    for path in paths:
        if is_file(path):
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
    print("PHP CS Fixer: {}".format(msg))


def format_contents(contents):
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
        format_file(tmp_file)
        with open(tmp_file, 'rb') as file:
            content = file.read().decode(encoding)
            file.close()
    finally:
        os.close(fd)
        os.remove(tmp_file)
    
    return content


def format_file(tmp_file):
    settings = load_settings()
    
    path = settings.get('path')
    
    if not path:
        path = locate_php_cs_fixer()
    
    if not path:
        raise ExecutableNotFoundException("Couldn't find php-cs-fixer")
    if not is_file(path):
        raise ExecutableNotFoundException("Couldn't execute file: {}".format(path))
    
    config = settings.get('config')
    rules = settings.get('rules')
    
    cmd = [path, "fix", "--using-cache=off", tmp_file]
    
    if config:
        variables = sublime.active_window().extract_variables()
        if 'folder' in variables:
            config = config.replace('${folder}', variables['folder'])
        
        cmd.append('--config=' + config)
        log_to_console("Using config: " + config)
    
    if rules:
        if isinstance(rules, list):
            rules = rules.join(",")
        
        if isinstance(rules, str):
            cmd.append("--rules=" + rules)
            log_to_console("Using rules: " + rules)
    
    p = create_process_for_platform(cmd)
    output, err = p.communicate()
    
    if p.returncode != 0:
        log_to_console("There was an error formatting the view")
        log_to_console("Command: {}".format(cmd))
        log_to_console("Error output: {}".format(err))


def create_process_for_platform(cmd):
    if is_windows():
        # We need to hide the console window
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        si = None
    
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, startupinfo=si)


class SublimePhpCsFixCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        try:
            log_to_console("Formatting view...")
            region = sublime.Region(0, self.view.size())
            contents = self.view.substr(region)
            
            if contents:
                formatted = format_contents(contents)
                if formatted and formatted != contents:
                    self.view.replace(edit, region, formatted)
                    log_to_console("Done. View formatted")
                else:
                    log_to_console("Done. No changes")
            else:
                log_to_console("Done. No contents")
        except ExecutableNotFoundException as e:
            log_to_console(str(e))


class SublimePhpCsFixListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        if setting_enabled('on_save'):
            view.run_command('sublime_php_cs_fix')
    
    def on_load(self, view):
        if setting_enabled('on_load'):
            view.run_command('sublime_php_cs_fix')


class ExecutableNotFoundException(BaseException):
    pass
