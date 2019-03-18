# Sublime PHP CS Fixer
This is a plugin for Sublime Text 3 to format PHP code through php-cs-fixer command on any view.

# Features

* It works inside a temporal view (ie: on an new, non-saved file)
* Fast
* Easy
* Configurable through rules or a config file
* Tested on Windows and Linux

# Configuration

You have to install the actual php-cs-fixer (the actual tool made by sensiolabs, not this plugin)

You can install php-cs-fixer directly with composer by running:

    composer global require friendsofphp/php-cs-fixer

Also you can create a config file as explained here https://github.com/FriendsOfPHP/PHP-CS-Fixer

*for example in:* `$HOME/.phpcsfixer`

    <?php
    return PhpCsFixer\Config::create()
    ->setRules([
        '@Symfony' => true,
        'array_syntax' => ['syntax' => 'short'],
    ]);

If you've created a config file, you have to configure its path in the plugin's settings.

*In Menu -> Preferences -> Package Settings -> PHP CS Fixer -> Settings - user*

    {
        "config": "/path/to/.phpcsfixer"
    }

When using multiple projects with different configurations, it's possible to configure the path relative to the Sublime project folder:

    {
        "config": "${folder}/.php_cs.dist"
    }

It's also possible to specify multiple config paths. In that case, the first readable file is used:

    {
        "config": [
            "${file_path}/.php_cs",
            "${file_path}/.php_cs.dist",
            "${folder}/.php_cs",
            "${folder}/.php_cs.dist",
            "/path/to/.phpcsfixer"
        ]
    }

See [`extract_variables` in the Sublime API Reference](https://www.sublimetext.com/docs/3/api_reference.html#sublime.Window) for the supported replacement variables. The value of the `${folder}` points the path of the first project in Sublime API. Here, it's beforehand replaced with the path of the project the target file belongs.

Please note that this plugin don't try to find the config file automatically. If you want to create a config file, you have to specify its path in the plugin settings.

Although you can configure the rules directly on your plugin settings, it's recommended to create the config file, as it's easier to configure every rule than using the 'rules' directive in the plugin settings.

## Exclude files

Since all php files are passed directly to the php-cs-fixer executable, a configured PhpCsFixer\\Finder gets ignored.
In order to exclude files from php-cs-fixer, you can use the "exclude" setting:

    {
        "exclude": [
            ".*[\\\\/]vendor[\\\\/].*", // vendor-path (used by Composer)
            ".*\\.phtml$" // files ending with ".phtml"
        ]
    }

The exclude-filter uses python regular expressions.
For more information see: https://docs.python.org/2/library/re.html


### On Windows:

The plugin tries to find the executable in:

    %APPDATA%\composer\vendor\bin\php-cs-fixer.bat

If it isn't working, you can locate your composer global packages path by running:

    composer config -g home

### On Linux:

After installing php-cs-fixer you have to specify the full path to the
executable in the configuration page.

The plugin tries to find the executable in:

    $HOME/.composer/vendor/bin/php-cs-fixer

However, if it isn't working, you can create a symbolic link to the php-cs-fixer executable

    ln -s $HOME/.composer/vendor/bin/php-cs-fixer $HOME/bin/php-cs-fixer

### Note

I've checked this on Linux and Windows, but I cannot check it on OSX.
I'll thank you if someone tells me if it's working on OSX and give me
some details on how to configure it.

# Acknowledgements

I would like to thank to sensiolabs and contributors for their awesome package
it works flawlessly. All the work here belongs to them.

Check them at:

* https://github.com/FriendsOfPHP/PHP-CS-Fixer
* http://cs.sensiolabs.org/

I'd also learned some of the sublime package structure from:

* https://github.com/Ennosuke/PHP-Codebeautifier
