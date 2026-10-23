# nuitka-project: --module
# nuitka-project: --output-dir=.\plugins
## nuitka-project: --no-pyi-file
# nuitka-project: --remove-output
# nuitka-project: --jobs=32

# nuitka-project: --include-module=core.plugin_base
# nuitka-project: --include-module=ui.custom_popup
# nuitka-project: --include-module=ui.cursor_follower
# nuitka-project: --include-module=plugins.core
# nuitka-project: --follow-import-to=plugins

## nuitka-project: --include-module=core.findit_worker
## nuitka-project: --include-module=requests
## nuitka-project: --include-module=requests.packages
## nuitka-project: --include-module=bs4
# nuitka-project: --include-package=plugins.win_mouse_gesture

## nuitka-project: --follow-import-to=bs4
## nuitka-project: --follow-import-to=webbrowser
## nuitka-project: --follow-import-to=urllib3,email,http,hmac,queue
## nuitka-project: --follow-import-to=requests

##  nuitka-project: --include-package=requests
##  nuitka-project: --include-package=urllib3
# nuitka-project: --report=compilation_report.xml

# execute "python -m nuitka clipboard_findit.py" from "MAIN DIR"

from .win_mouse_plugin import WinGesture


def create_plugin():
    return WinGesture
