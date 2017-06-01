import sublime, sublime_plugin, subprocess
import os, tempfile


def load_settings():
    return sublime.load_settings("SublimePhpCsFixer.sublime-settings")


class SublimePhpCsFixCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        region = sublime.Region(0, self.view.size())
        contents = self.view.substr(region)

        if contents:
            formatted = self.fix(contents)
            if formatted:
                self.view.replace(edit, region, formatted)

    def fix(self, contents):
        os_handle, tmp_file = tempfile.mkstemp()

        with open(tmp_file, 'wb') as file:
            file.write(contents.encode('utf8'))

        self.format_file(tmp_file)

        with open(tmp_file, 'r') as file:
            content = file.read()

        os.unlink(tmp_file)

        return content

    def format_file(self, tmp_file):
        settings = load_settings()

        cmd = []
        path = settings.get('path')
        rules = settings.get('rules')

        if not path:
            path = "php-cs-fixer"

        cmd.append(path)
        cmd.append("fix")
        cmd.append(tmp_file)

        if rules:
            if isinstance(rules, list):
                rules = rules.join(",")
            cmd.append("--rules=" + rules)

        subprocess.call(cmd)


class SublimePhpCsFixListener(sublime_plugin.EventListener):

    def on_post_save(self, view):
        if self.setting_enabled('on_save'):
            view.run_command('sublime_php_cs_fix')

    def on_load(self, view):
        if self.setting_enabled('on_load'):
            view.run_command('sublime_php_cs_fix')

    def setting_enabled(self, name):
        return load_settings().get(name)
