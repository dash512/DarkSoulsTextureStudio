import shlex
import re
import logging
from pprint import pformat
from pathlib import Path
from copy import deepcopy
from DSTS.Dataclasses import Command
from DSTS.log_utils import format_exc_clean, formatter
from soulstruct.containers.tpf import TPFPlatform
from soulstruct.base.textures.dds import DDS
from soulstruct.base.textures.dds.swizzle import swizzle_dds_bytes_ps4
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QCompleter, QVBoxLayout, QWidget, QFileDialog
from PySide6.QtCore import Qt

class ConsoleWindow(QWidget):
    def __init__(self, parent, emitter):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle("Console")
        self.setGeometry(400, 300, 750, 600)
        self.commands = {
            "help": Command(self.cmd_help, "Prints help message"),
            "clear": Command(self.cmd_clear, "Clears console"),
            "objects": Command(self.cmd_objects, "List available objects. Calling an object will return its repr"),
            "ls": Command(self.cmd_ls, "Lists all items in an iterable"),
            "repr": Command(self.cmd_repr, "Calls __repr__() for an object"),
            "len": Command(self.cmd_len, "Prints length/amount of items in an iterable"),
            "verbose": Command(self.cmd_verbose, "Toggles verbosity, showing DEBUG level logs to console"),
            "xp_swl": Command(self.cmd_export_swizzled, "Exports a swizzled version of the currently selected PS4 texture for debug"),
            "python": Command(self.cmd_dbg, "Toggles debug mode, allowing code execution. Only do this if you know what you're doing."),
        }

        self.objects = {}
        self._TOKEN_RE = re.compile(r"""
            ([A-Za-z_]\w*)      |   # name
            \[([^\]]+)\]        |   # scripting
            \.([A-Za-z_]\w*)        # property
        """, re.X)

        self.devmode = False
        self.level = logging.INFO

        self.display = QPlainTextEdit()
        self.display.setReadOnly(True)

        self.command = QLineEdit()
        self.command.setPlaceholderText(">>> help")
        completer = QCompleter([
            "help",
            "clear",
            "objects",
            "ls",
            "repr",
            "len",
            "verbose",
            "xp_swl",
            "python"
        ])
        self.command.setCompleter(completer)
        self.command.returnPressed.connect(self.execute_command)

        layout = QVBoxLayout(self)
        layout.addWidget(self.display)
        layout.addWidget(self.command)

        emitter.message.connect(self.append_record)

    def println(self, text=""):
        self.display.appendPlainText(str(text))

    def console_print(self, *args, **kwargs):
        self.println(" ".join(map(str, args)))

    def set_objects(self, **objects):
        self.objects = objects
    
    def resolve(self, expr):
        pos = 0

        m = self._TOKEN_RE.match(expr)
        if not m or m.group(1) is None:
            raise ValueError("Expected object name")

        obj = self.objects.get(m.group(1))
        if obj is None:
            raise ValueError(f"Unknown object '{m.group(1)}'")
        if callable(obj):
            obj = obj()

        pos = m.end()

        while pos < len(expr):
            m = self._TOKEN_RE.match(expr, pos)
            if not m:
                raise ValueError(f"Unexpected syntax near '{expr[pos:]}'")

            token = m.group(0)

            if token.startswith("."):
                obj = getattr(obj, token[1:])

            else:
                key = token[1:-1].strip()

                try:
                    key = int(key)
                except ValueError:
                    if (len(key) >= 2 and ((key[0] == key[-1] == "'") or (key[0] == key[-1] == '"'))):
                        key = key[1:-1]

                    elif key in self.objects:
                        key = self.resolve(key)

                if isinstance(obj, dict) and isinstance(key, int):
                    obj = list(obj.values())[key]
                else:
                    obj = obj[key]

            pos = m.end()

        return obj

    def append_record(self, record):
        if record.levelno < self.level:
            return

        self.println(f"{record.levelname}: {formatter.format(record)}")

    def execute_command(self):
        text = self.command.text().strip()
        self.command.clear()

        if not text:
            return

        self.println(f">>> {text}")

        parts = shlex.split(text, posix=True)
        cmd = parts[0]
        arg = " ".join(parts[1:])

        entry = self.commands.get(cmd)
        if entry is not None:
            entry.func(arg)
            return

        try:
            obj = self.resolve(text)
            self.println(repr(obj))
            return
        except Exception:
            pass

        if self.devmode:
            self.execute_python(text)
            return

        self.println(f"Unknown command '{text}'")

    def execute_python(self, text):
        namespace = {
            name: obj() if callable(obj) else obj
            for name, obj in self.objects.items()
        }

        globals = {
            "__builtins__": __builtins__,
            "print": self.console_print,
        }

        try:
            try:
                result = eval(text, globals, namespace)
            except SyntaxError:
                exec(text, globals, namespace)
                return

            if result is not None:
                self.println(pformat(result))

        except Exception:
            self.println(format_exc_clean())

    def cmd_export_swizzled(self, arg=None):
        game = self.objects["game"]().name
        if game != 'Bloodborne':
            self.println("Selection is not a valid PS4 texture")
            return
        name = self.objects["current"]()
        atlas = self.objects['atlases']()[name]
        tex = deepcopy(atlas.texture)

        output = Path(QFileDialog.getSaveFileName(self, "Save To", "debug.dds", "DDS Files (*.dds)")[0])
        if output and output != Path('.'):
            dds = DDS.from_bytes(tex.get_headerized_data(TPFPlatform.PC))
            data = swizzle_dds_bytes_ps4(
                deswizzled=dds.data,
                dxgi_format=tex.console_info.dxgi_format,
                width=tex.console_info.width,
                height=tex.console_info.height,
            )   
            swizzled_dds = DDS(header=dds.header, dx10_header=dds.dx10_header, data=data)  
            swizzled_dds.write(output)
            self.println(f"Wrote swizzled and headerized DDS to:\n{output}")

    def cmd_help(self, arg=None):
        self.println("Available commands:")

        for name, cmd in self.commands.items():
            self.println(f"  {name} - {cmd.help}")

    def cmd_ls(self, name):
        obj = self.resolve(name)

        if obj is None:
            self.println("Unknown object")
            return

        try:
            for item in obj:
                self.println(str(item))
        except TypeError:
            self.println(f"{name} is not iterable")
    
    def cmd_dbg(self, arg=None):
        self.devmode = not self.devmode

        if self.devmode:
            self.println("Developer mode enabled.")
        else:
            self.println("Developer mode disabled.")

    def cmd_verbose(self, arg=None):
        if self.level == logging.INFO:
            self.level = logging.DEBUG
            self.println("Verbose logging enabled.")
        else:
            self.level = logging.INFO
            self.println("Verbose logging disabled.")

    def cmd_repr(self, name):
        obj = self.resolve(name)

        if obj is None:
            self.println("Unknown object")
            return

        self.println(repr(obj))

    def cmd_len(self, name):
        obj = self.resolve(name)

        if obj is None:
            self.println("Unknown object")
            return

        self.println(str(len(obj)))

    def cmd_objects(self, arg=None):
        for name in sorted(self.objects):
            self.println(name)

    def cmd_clear(self, arg=None):
        self.display.clear()
