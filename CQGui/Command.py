# -*- coding: utf-8 -*-
"""Adds all of the commands that are used for the menus of the CadQuery module"""
# (c) 2014-2016 Jeremy Wright Apache 2.0 License

import imp, os, sys, tempfile
import FreeCAD, FreeCADGui
from PySide import QtGui, QtCore
import ExportCQ, ImportCQ
import module_locator
import Settings
import Shared
from random import random
from contextlib import contextmanager
from cadquery import cqgi
from Helpers import show

# Distinguish python built-in open function from the one declared here
if open.__module__ == '__builtin__':
    pythonopen = open


@contextmanager
def revert_sys_modules():
    """
    Remove any new modules after context has exited
    >>> with revert_sys_modules():
    ...     import some_module
    ...     some_module.do_something()
    >>> some_module.do_something()  # raises NameError: name 'some_module' is not defined
    """
    modules_before = set(sys.modules.keys())
    try:
        yield
    finally:
        # irrespective of the succes of the context's execution, new modules
        # will be deleted upon exit
        for mod_name in sys.modules.keys():
            if mod_name not in modules_before:
                del sys.modules[mod_name]


class CadQueryClearOutput:
    """Allows the user to clear the reports view when it gets overwhelmed with output"""

    def GetResources(self):
        return {"MenuText": "Clear Output",
                "Accel": "Shift+Alt+C",
                "ToolTip": "Clears the script output from the Reports view",
                "Pixmap": ":/icons/button_invalid.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        # Grab our main window so we can interact with it
        mw = FreeCADGui.getMainWindow()

        reportView = mw.findChild(QtGui.QDockWidget, "Report view")

        # Clear the view because it gets overwhelmed sometimes and won't scroll to the bottom
        reportView.widget().clear()


class CadQueryCloseScript:
    """Allows the user to close a file without saving"""

    def GetResources(self):
        return {"MenuText": "Close Script",
                "ToolTip": "Closes the CadQuery script",
                "Pixmap": ":/icons/edit_Cancel.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        mw = FreeCADGui.getMainWindow()

        # Grab our code editor so we can interact with it
        cqCodePane = Shared.getActiveCodePane()

        # If there's nothing open in the code pane, we don't need to close it
        if cqCodePane is None or len(cqCodePane.file.path) == 0:
            return

        # Check to see if we need to save the script
        if cqCodePane.dirty:
            reply = QtGui.QMessageBox.question(cqCodePane, "Save CadQuery Script", "Save script before closing?",
                                               QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel)

            if reply == QtGui.QMessageBox.Cancel:
                return

            if reply == QtGui.QMessageBox.Yes:
                # If we've got a file name already save it there, otherwise give a save-as dialog
                if len(cqCodePane.file.path) == 0:
                    filename = QtGui.QFileDialog.getSaveFileName(mw, mw.tr("Save CadQuery Script As"), "/home/",
                                                                 mw.tr("CadQuery Files (*.py)"))
                else:
                    filename = cqCodePane.file.path

                # Make sure we got a valid file name
                if filename is not None:
                    ExportCQ.save(filename)

        Shared.closeActiveCodeWindow()

class CadQueryOpenExample:
    exFile = None

    def __init__(self, exFile):
        self.exFile = str(exFile)

    def GetResources(self):
        return {"MenuText": str(self.exFile),
                "Pixmap": ":/icons/accessories-text-editor.svg"}

    def Activated(self):
        FreeCAD.Console.PrintMessage(self.exFile + "\r\n")

        # So we can open the "Open File" dialog
        mw = FreeCADGui.getMainWindow()

        # Start off defaulting to the Examples directory
        module_base_path = module_locator.module_path()
        exs_dir_path = os.path.join(module_base_path, 'Libs/cadquery/examples/FreeCAD')

        # Append this script's directory to sys.path
        sys.path.append(os.path.dirname(exs_dir_path))

        # We've created a library that FreeCAD can use as well to open CQ files
        ImportCQ.open(os.path.join(exs_dir_path, self.exFile))


class CadQueryExecuteScript:
    """CadQuery's command to execute a script file"""

    def GetResources(self):
        return {"MenuText": "Execute Script",
                "Accel": Settings.execute_keybinding,
                "ToolTip": "Executes the CadQuery script",
                "Pixmap": ":/icons/media-playback-start.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        # Grab our code editor so we can interact with it
        cqCodePane = Shared.getActiveCodePane()

        # Clear the old render before re-rendering
        Shared.clearActiveDocument()

        scriptText = cqCodePane.toPlainText().encode('utf-8')

        # Check to see if we are executig a CQGI compliant script
        if ("show_object(" in scriptText and "# show_object(" not in scriptText and "#show_boject(" not in scriptText) or ("debug(" in scriptText and "# debug(" not in scriptText and "#debug(" not in scriptText):
            FreeCAD.Console.PrintMessage("Executing CQGI-compliant script.\r\n")

            # A repreentation of the CQ script with all the metadata attached
            cqModel = cqgi.parse(scriptText)

            # Allows us to present parameters to users later that they can alter
            parameters = cqModel.metadata.parameters
            build_parameters = {}

            # Collect the build parameters from the Parameters Editor view, if they exist
            mw = FreeCADGui.getMainWindow()

            # Tracks whether or not we have already added the variables editor
            isPresent = False

            # If the widget is open, we need to close it
            dockWidgets = mw.findChildren(QtGui.QDockWidget)
            for widget in dockWidgets:
                if widget.objectName() == "cqVarsEditor":
                    # Toggle the visibility of the widget
                    if not widget.visibleRegion().isEmpty():
                        # Find all of the controls that will have parameter values in them
                        valueControls = mw.findChildren(QtGui.QLineEdit)
                        for valueControl in valueControls:
                            objectName = valueControl.objectName()

                            # We only want text fields that will have parameter values in them
                            if objectName != None and objectName != '' and objectName.find('pcontrol_') >= 0:
                                # Associate the value in the text field with the variable name in the script
                                build_parameters[objectName.replace('pcontrol_', '')] = valueControl.text()

            build_result = cqModel.build(build_parameters=build_parameters)

            # Make sure that the build was successful
            if build_result.success:
                # Display all the results that the user requested
                for result in build_result.results:
                    # Apply options to the show function if any were provided
                    if result.options and result.options["rgba"]:
                        show(result.shape, result.options["rgba"])
                    else:
                        show(result.shape)

                for debugObj in build_result.debugObjects:
                    # Mark this as a debug object
                    debugObj.shape.val().label = "Debug" + str(random())

                    # Apply options to the show function if any were provided
                    if debugObj.options and debugObj.options["rgba"]:
                        show(debugObj.shape, debugObj.options["rgba"])
                    else:
                        show(debugObj.shape, (255, 0, 0, 0.80))
            else:
                FreeCAD.Console.PrintError("Error executing CQGI-compliant script. " + str(build_result.exception) + "\r\n")
        else:
            # Save our code to a tempfile and render it
            tempFile = tempfile.NamedTemporaryFile(delete=False)
            tempFile.write(scriptText)
            tempFile.close()

            # Set some environment variables that may help the user
            os.environ["MYSCRIPT_FULL_PATH"] = cqCodePane.file.path
            os.environ["MYSCRIPT_DIR"] = os.path.dirname(os.path.abspath(cqCodePane.file.path))

            # We import this way because using execfile() causes non-standard script execution in some situations
            with revert_sys_modules():
                imp.load_source('temp_module', tempFile.name)

        msg = QtGui.QApplication.translate(
            "cqCodeWidget",
            "Executed ",
            None)
        FreeCAD.Console.PrintMessage(msg + cqCodePane.file.path + "\r\n")


class CadQueryNewScript:
    """CadQuery's command to start a new script file."""
    def GetResources(self):
        return {"MenuText": "New Script",
                "Accel": "Alt+N",
                "ToolTip": "Starts a new CadQuery script",
                "Pixmap": ":/icons/document-new.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        module_base_path = module_locator.module_path()
        templ_dir_path = os.path.join(module_base_path, 'Templates')

        # Use the library that FreeCAD can use as well to open CQ files
        ImportCQ.open(os.path.join(templ_dir_path, 'script_template.py'))

        FreeCAD.Console.PrintMessage("Please save this template file as another name before creating any others.\r\n")


class CadQueryOpenScript:
    """CadQuery's command to open a script file."""
    previousPath = None

    def GetResources(self):
        return {"MenuText": "Open Script",
                "Accel": "Alt+O",
                "ToolTip": "Opens a CadQuery script from disk",
                "Pixmap": ":/icons/document-open.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        # So we can open the "Open File" dialog
        mw = FreeCADGui.getMainWindow()

        # Try to keep track of the previous path used to open as a convenience to the user
        if self.previousPath is None:
            # Start off defaulting to the Examples directory
            module_base_path = module_locator.module_path()
            exs_dir_path = os.path.join(module_base_path, 'Libs/cadquery/examples/FreeCAD')

            self.previousPath = exs_dir_path

        filename = QtGui.QFileDialog.getOpenFileName(mw, mw.tr("Open CadQuery Script"), self.previousPath,
                                                     mw.tr("CadQuery Files (*.py)"))

        # Make sure the user didn't click cancel
        if filename[0]:
            self.previousPath = filename[0]

            # Append this script's directory to sys.path
            sys.path.append(os.path.dirname(filename[0]))

            # We've created a library that FreeCAD can use as well to open CQ files
            ImportCQ.open(filename[0])


class CadQuerySaveScript:
    """CadQuery's command to save a script file"""

    def GetResources(self):
        return {"MenuText": "Save Script",
                "Accel": "Alt+S",
                "ToolTip": "Saves the CadQuery script to disk",
                "Pixmap": ":/icons/document-save.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        # Grab our code editor so we can interact with it
        cqCodePane = Shared.getActiveCodePane()

        # If there are no windows open there is nothing to save
        if cqCodePane == None:
            FreeCAD.Console.PrintError("Nothing to save.\r\n")
            return

        # If the code pane doesn't have a filename, we need to present the save as dialog
        if len(cqCodePane.file.path) == 0 or os.path.basename(cqCodePane.file.path) == 'script_template.py' \
                or os.path.split(cqCodePane.file.path)[0].endswith('FreeCAD'):
            FreeCAD.Console.PrintError("You cannot save over a blank file, example file or template file.\r\n")

            CadQuerySaveAsScript().Activated()

            return

        # Rely on our export library to help us save the file
        ExportCQ.save()

        # Execute the script if the user has asked for it
        if Settings.execute_on_save:
            CadQueryExecuteScript().Activated()

class CadQuerySaveAsScript:
    """CadQuery's command to save-as a script file"""
    previousPath = None

    def GetResources(self):
        return {"MenuText": "Save Script As",
                "Accel": "",
                "ToolTip": "Saves the CadQuery script to disk in a location other than the original",
                "Pixmap": ":/icons/document-save-as.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        # So we can open the save-as dialog
        mw = FreeCADGui.getMainWindow()
        cqCodePane = Shared.getActiveCodePane()

        if cqCodePane == None:
            FreeCAD.Console.PrintError("Nothing to save.\r\n")
            return

        # Try to keep track of the previous path used to open as a convenience to the user
        if self.previousPath is None:
            self.previousPath = "/home/"

        filename = QtGui.QFileDialog.getSaveFileName(mw, mw.tr("Save CadQuery Script As"), self.previousPath,
                                                     mw.tr("CadQuery Files (*.py)"))

        self.previousPath = filename[0]

        # Make sure the user didn't click cancel
        if filename[0]:
            # Close the 3D view for the original script if it's open
            try:
                docname = os.path.splitext(os.path.basename(cqCodePane.file.path))[0]
                FreeCAD.closeDocument(docname)
            except:
                # Assume that there was no 3D view to close
                pass

            # Change the name of our script window's tab
            Shared.setActiveWindowTitle(os.path.basename(filename[0]))

            # Save the file before closing the original and the re-rendering the new one
            ExportCQ.save(filename[0])
            CadQueryExecuteScript().Activated()


class ToggleParametersEditor:
    """If the user is running a CQGI-compliant script, they can edit variables through this edistor"""

    def GetResources(self):
        return {"MenuText": "Toggle Parameters Editor",
                "Accel": "Shift+Alt+E",
                "ToolTip": "Opens a live variables editor editor",
                "Pixmap": ":/icons/edit-edit.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        mw = FreeCADGui.getMainWindow()

        # Tracks whether or not we have already added the variables editor
        isPresent = False

        # If the widget is open, we need to close it
        dockWidgets = mw.findChildren(QtGui.QDockWidget)
        for widget in dockWidgets:
            if widget.objectName() == "cqVarsEditor":
                # Toggle the visibility of the widget
                if widget.visibleRegion().isEmpty():
                    widget.setVisible(True)
                else:
                    widget.setVisible(False)

                isPresent = True

        if not isPresent:
            cqVariablesEditor = QtGui.QDockWidget("CadQuery Variables Editor")
            cqVariablesEditor.setObjectName("cqVarsEditor")

            mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, cqVariablesEditor)

        # Go ahead and populate the view if there are variables in the script
        CadQueryValidateScript().Activated()


class CadQueryValidateScript:
    """Checks the script for the user without executing it and populates the variable editor, if needed"""

    def GetResources(self):
        return {"MenuText": "Validate Script",
                "Accel": "F4",
                "ToolTip": "Validates a CadQuery script",
                "Pixmap": ":/icons/edit_OK.svg"}

    def IsActive(self):
        return True

    def Activated(self):
        # Grab our code editor so we can interact with it
        cqCodePane = Shared.getActiveCodePane()

        # If there is no script to check, ignore this command
        if cqCodePane is None:
            FreeCAD.Console.PrintMessage("There is no script to validate.")
            return

        # Clear the old render before re-rendering
        Shared.clearActiveDocument()

        scriptText = cqCodePane.toPlainText().encode('utf-8')

        if ("show_object(" not in scriptText and "# show_object(" in scriptText and "#show_boject(" in scriptText) or ("debug(" not in scriptText and "# debug(" in scriptText and "#debug(" in scriptText):
            FreeCAD.Console.PrintError("Script did not call show_object or debug, no output available. Script must be CQGI compliant to get build output, variable editing and validation.\r\n")
            return

        # A repreentation of the CQ script with all the metadata attached
        cqModel = cqgi.parse(scriptText)

        # Allows us to present parameters to users later that they can alter
        parameters = cqModel.metadata.parameters

        Shared.populateParameterEditor(parameters)
