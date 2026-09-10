from cx_Freeze import setup, Executable, build_exe
import sys, os, shutil

class CustomBuild(build_exe):
    def run(self):
        super().run()

        translations = os.path.join(
            self.build_exe,
            "lib",
            "PySide6",
            "translations"
        )

        if os.path.exists(translations):
            shutil.rmtree(translations)

include_files = [
    ("icon.ico", "icon.ico"),
    ("defs", "defs"),
    ("soulstruct/base/textures/texconv.exe", "texconv.exe"),
    ("README.md", "README.md"),
    ("LICENSE", "LICENSE")
]

packages = ["soulstruct", "DSTextureStudio"]

build_exe_options = {
    "packages": packages,
    "include_files": include_files,
    "include_msvcr": True,

    "excludes": [
        "PySide6.QtPrintSupport", 
        "PySide6.QtSql", 
        "PySide6.QtNetwork", 
        "PySide6.QtTest", 
        "PySide6.QtConcurrent", 
        "PySide6.QtDBus", 
        "PySide6.QtDesigner", 
        "PySide6.QtXml", 
        "PySide6.QtHelp", 
        "PySide6.QtMultimedia", 
        "PySide6.QtMultimediaWidgets", 
        "PySide6.QtOpenGL", 
        "PySide6.QtOpenGLWidgets", 
        "PySide6.QtPdf", 
        "PySide6.QtPdfWidgets", 
        "PySide6.QtPositioning", 
        "PySide6.QtLocation", 
        "PySide6.QtNetworkAuth", 
        "PySide6.QtNfc", 
        "PySide6.QtQml", 
        "PySide6.QtQuick", 
        "PySide6.QtQuick3D", 
        "PySide6.QtQuickControls2", 
        "PySide6.QtQuickTest", 
        "PySide6.QtQuickWidgets", 
        "PySide6.QtRemoteObjects", 
        "PySide6.QtScxml", 
        "PySide6.QtSensors", 
        "PySide6.QtSerialPort", 
        "PySide6.QtSerialBus", 
        "PySide6.QtStateMachine", 
        "PySide6.QtTextToSpeech", 
        "PySide6.QtCharts", 
        "PySide6.QtSpatialAudio", 
        "PySide6.QtSvg", 
        "PySide6.QtSvgWidgets", 
        "PySide6.QtDataVisualization", 
        "PySide6.QtGraphs", 
        "PySide6.QtGraphsWidgets", 
        "PySide6.QtBluetooth", 
        "PySide6.QtUiTools", 
        "PySide6.QtAxContainer", 
        "PySide6.QtWebChannel", 
        "PySide6.QtWebEngineCore", 
        "PySide6.QtWebEngineWidgets", 
        "PySide6.QtWebEngineQuick", 
        "PySide6.QtWebSockets", 
        "PySide6.QtHttpServer", 
        "PySide6.QtWebView", 
        "PySide6.Qt3DCore", 
        "PySide6.Qt3DRender", 
        "PySide6.Qt3DInput", 
        "PySide6.Qt3DLogic", 
        "PySide6.Qt3DAnimation", 
        "PySide6.Qt3DExtras",

        "PIL._avif",

        "numpy",
        "tkinter",
        "unittest",
        "test",
        "pydoc",
        "doctest",
        "email",
        "xmlrpc",
        "http",
    ],

    "bin_excludes": [
        "PySide6/translations",
        "PySide6/Qt6Pdf.dll",
        "PySide6/Qt6Qml.dll",
        "PySide6/Qt6QmlModels.dll",
        "PySide6/Qt6QmlMeta.dll",
        "PySide6/Qt6QmlWorkerScript.dll",
        "PySide6/Qt6Quick.dll",
        "PySide6/Qt6QuickWidgets.dll",
        "PySide6/Qt6VirtualKeyboard.dll",
        "PySide6/Qt6OpenGL.dll",
        "PySide6/Qt6Network.dll "
    ],

    "zip_include_packages": ["*"],
    "zip_exclude_packages": ["PySide6"],
}

base = None
if sys.platform == "win32":
    base = "GUI"

setup(
    name="DSTS",
    version="3.10.4",
    description="Dark Souls Texture Studio",
    options={"build_exe": build_exe_options},
    cmdclass={"build_exe": CustomBuild},
    executables=[Executable("DSTS.py", base=base, icon="icon.ico")],
)