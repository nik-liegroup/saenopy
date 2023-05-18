import json
import sys
import os
import matplotlib as mpl
from typing import List
import matplotlib.pyplot as plt
from qtpy import QtCore, QtWidgets
import numpy as np

from saenopy.gui.common import QtShortCuts
from saenopy.gui.common.resources import resource_icon
from saenopy.gui.solver.analyze.plot_window import PlottingWindow
from saenopy.gui.solver.modules.BatchEvaluate import BatchEvaluate
from saenopy.gui.common.gui_classes import ListWidget
from saenopy.gui.common.gui_classes import CheckAbleGroup, MatplotlibWidget, NavigationToolbar
from saenopy import macro

class Parameter(QtWidgets.QWidget):
    valueChanged = QtCore.Signal()
    def __init__(self, name, value, allow_none):
        super().__init__(None)
        self.name = name
        with QtShortCuts.QHBoxLayout(self):
            self.label_name = QtWidgets.QLabel(name).addToLayout()
            with QtShortCuts.QVBoxLayout():
                with QtShortCuts.QHBoxLayout():
                    self.input = QtShortCuts.QInputString(None, "start", str(value), type=float, allow_none=allow_none, none_value=None).addToLayout()
                    self.input.valueChanged.connect(self.valueChanged)
                    self.input.line_edit.setMaximumWidth(70)
                    self.bool = QtShortCuts.QInputBool(None, "none", False).addToLayout()
                    self.bool.valueChanged.connect(self.setNone)
                    self.bool.setEnabled(allow_none)
                with QtShortCuts.QHBoxLayout():
                    self.input2 = QtShortCuts.QInputString(None, "fitted", "").addToLayout()
                    self.input2.line_edit.setReadOnly(True)
                    self.input2.line_edit.setMaximumWidth(70)
                    self.bool2 = QtShortCuts.QInputBool(None, "const", False).addToLayout()
                    self.bool2.valueChanged.connect(self.setConst)

        self.value = value

    def setNone(self):
        if self.bool.value() == True:
            self.value = self.input.value()
            self.input.setValue("None")
            self.input.setDisabled(True)
            self.bool2.setDisabled(True)
            self.input2.setDisabled(True)
        else:
            self.input.setValue(self.value)
            self.input.setDisabled(False)
            self.bool2.setDisabled(False)
            self.input2.setDisabled(False)
            self.setConst()

    def setConst(self):
        if self.bool2.value() == True:
            self.input2.setDisabled(True)
        else:
            self.input2.setDisabled(False)

class AllParameters(QtWidgets.QWidget):
    valueChanged = QtCore.Signal()

    def __init__(self):
        super().__init__(None)
        with QtShortCuts.QHBoxLayout(self):
             self.layouts = [
                 QtShortCuts.QVBoxLayout(),
                 QtShortCuts.QVBoxLayout(),
                 QtShortCuts.QVBoxLayout(),
                 QtShortCuts.QVBoxLayout(),
             ]
        self.param_inputs: List[List[Parameter]] = []

    def setParams(self, params):
        for i, group in enumerate(self.param_inputs):
            for obj in group:
                self.layouts[i].removeWidget(obj)
        self.param_inputs = [[], [], [], []]

        for (i, name), value in params.items():
            with self.layouts[i]:
                self.param_inputs[i].append(Parameter(name, value, allow_none=i!=0).addToLayout())
    def value(self):
        values = {}
        for i, group in enumerate(self.param_inputs):
            for obj in group:
                try:
                    values[i, obj.name] = obj.input.value()
                except ValueError:
                    raise ValueError(f"Parameter {obj.name} does contain invalid value '{obj.input.line_edit.text()}'")
        return values

    def valuesFixed(self):
        values = {}
        for i, group in enumerate(self.param_inputs):
            for obj in group:
                values[i, obj.name] = obj.bool2.value() or obj.bool.value() or obj.input.value() is None
        return values

    def setFitted(self, value):
        for (i, n), v in value.items():
            for p in self.param_inputs[i]:
                if p.name == n:
                    p.input2.setValue(v)

class MainWindowFit(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        # QSettings
        self.settings = QtCore.QSettings("Saenopy", "Saenopy")

        with QtShortCuts.QHBoxLayout(self):
            with QtShortCuts.QVBoxLayout():
                self.input_type = QtShortCuts.QInputChoice(None, "type", "none", ["none", "shear rheometer", "stretch thinning", "extensional rheometer"]).addToLayout()
                self.input_type.setDisabled(True)
                self.input_type.valueChanged.connect(lambda x: self.set_value(x, "type"))

                self.input_params = QtShortCuts.QInputString(None, "params", "").addToLayout()
                self.input_params.setDisabled(True)
                self.input_params.valueChanged.connect(lambda x: self.set_value(x, "params"))

                self.list = ListWidget(QtShortCuts.current_layout, add_item_button="add measurements", color_picker=True)
                self.list.addItemClicked.connect(self.add_measurement)
                self.list.itemSelectionChanged.connect(self.listSelected)

            with QtShortCuts.QVBoxLayout():
                self.all_params = AllParameters().addToLayout()
                self.canvas = MatplotlibWidget(self).addToLayout()
                self.button_run = QtShortCuts.QPushButton(None, "run", self.run).addToLayout()

        self.params_index = 1
        self.data = []
        self.start_params = {}
        self.list.setData(self.data)
        def valueChanged():
            print("valueChanged",self.start_params)
            self.start_params = self.all_params.value()

        self.all_params.valueChanged.connect(valueChanged)

    def set_value(self, x, key):
        if key == "params":
            try:
                x = [i.strip() for i in x.split(",")]
                assert len(x) == 4
                self.input_params.line_edit.setStyleSheet("")
                for i, xx in enumerate(x):
                    if (i, xx) not in self.start_params:
                        self.start_params[i, xx] = self.start_params[i, self.data[self.list.currentRow()][2][key][i]]
            except AssertionError:
                self.input_params.line_edit.setStyleSheet("background: #d56060")
                return
        self.data[self.list.currentRow()][2][key] = x
        self.update_params()

    def listSelected(self):
        if self.list.currentRow() is not None and self.list.currentRow() < len(self.data):
            extra = self.data[self.list.currentRow()][2]
            self.input_type.setDisabled(False)
            self.input_type.setValue(extra["type"])

            self.input_params.setDisabled(False)
            self.input_params.setValue(", ".join(extra["params"]))
            #self.set_current_result.emit(pipe)

            self.update_params()

    def update_params(self):
        param_names = [{}, {}, {}, {}]
        all_params = {}
        for d in self.data:
            if d[1] and d[2]["type"] != "none":
                params = d[2]["params"]

                for i, p in enumerate(params):
                    p = p.strip()
                    if (i, p) not in all_params:
                        all_params[i, p] = self.start_params[i, p]
        self.all_params.setParams(all_params)

    def run(self):
        try:
            start_params = self.all_params.value()
        except ValueError as err:
            QtWidgets.QMessageBox.critical(self, "Load Stacks", str(err))
            return
        fixed_params = self.all_params.valuesFixed()

        parameter_set = []
        parameter_name_to_index = {}
        for d in self.data:
            if d[1] and d[2]["type"] != "none":
                for i, p in enumerate(d[2]["params"]):
                    if (i, p) not in parameter_set:
                        parameter_set.append((i, p))

        maps = {}
        param_start = []
        for (i, p) in parameter_set:
            if (i, p) in fixed_params and fixed_params[i, p]:
                maps[i, p] = lambda params, v=start_params[i, p]: v
            else:
                index = len(param_start)
                #parameter_name_to_index[i, p] = index
                maps[i, p] = lambda params, index=index: params[index]
                param_start.append(start_params[i, p])

        parts = []
        colors = []
        for d in self.data:
            if d[1] and d[2]["type"] != "none":
                colors.append(d[3])
                params = d[2]["params"]
                keys = []
                for i, p in enumerate(params):
                    keys.append((i, p))
                def set(params, keys=keys):
                    params_dict = {k: maps[k](params) for k in maps}
                    values = tuple([params_dict[k] for k in keys])
                    return values

                if d[2]["type"] == "shear rheometer":
                    parts.append([macro.get_shear_rheometer_stress, d[2]["data"], set])
                if d[2]["type"] == "stretch thinning":
                    parts.append([macro.get_stretch_thinning, d[2]["data"], set])
                if d[2]["type"] == "extensional rheometer":
                    parts.append([macro.get_extensional_rheometer_stress, d[2]["data"], set])

        params, plot = macro.minimize(parts,
            param_start,
            colors=colors
        )
        params_dict = {k: maps[k](params) for k in maps}
        print(params_dict)
        self.all_params.setFitted(params_dict)
        #self.final_param_values.setValue(json.dumps(results))
        plt.figure(self.canvas.figure)
        plt.clf()
        plot()
        self.canvas.draw()

    def add_measurement(self):
        new_path = QtWidgets.QFileDialog.getOpenFileName(None, "Load Session", os.getcwd(), "JSON File (*.json)")
        if new_path:
            self.add_file(new_path)

    def add_file(self, new_path):
        data = np.loadtxt(new_path)
        print(data.shape)
        params = [f"k{self.params_index}", f"d_0{self.params_index}", f"lambda_s{self.params_index}", f"d_s{self.params_index}"]
        self.list.addData(new_path, True, dict(data=data, type="none", params=params), mpl.colors.to_hex(f"C{len(self.data)}"))
        for i, param in enumerate(params):
            self.start_params[i, param.strip()] = [900, 0.0004, 0.075, 0.33][i]
        self.params_index += 1
        self.update_params()


if __name__ == '__main__':  # pragma: no cover

    data0_6 = np.array(
        [[4.27e-06, -2.26e-03], [1.89e-02, 5.90e-01], [3.93e-02, 1.08e+00], [5.97e-02, 1.57e+00], [8.01e-02, 2.14e+00],
         [1.00e-01, 2.89e+00], [1.21e-01, 3.83e+00], [1.41e-01, 5.09e+00], [1.62e-01, 6.77e+00], [1.82e-01, 8.94e+00],
         [2.02e-01, 1.17e+01], [2.23e-01, 1.49e+01], [2.43e-01, 1.86e+01], [2.63e-01, 2.28e+01], [2.84e-01, 2.71e+01]])
    data1_2 = np.array(
        [[1.22e-05, -1.61e-01], [1.71e-02, 2.57e+00], [3.81e-02, 4.69e+00], [5.87e-02, 6.34e+00], [7.92e-02, 7.93e+00],
         [9.96e-02, 9.56e+00], [1.20e-01, 1.14e+01], [1.40e-01, 1.35e+01], [1.61e-01, 1.62e+01], [1.81e-01, 1.97e+01],
         [2.02e-01, 2.41e+01], [2.22e-01, 2.95e+01], [2.42e-01, 3.63e+01], [2.63e-01, 4.43e+01], [2.83e-01, 5.36e+01],
         [3.04e-01, 6.37e+01], [3.24e-01, 7.47e+01], [3.44e-01, 8.61e+01], [3.65e-01, 9.75e+01], [3.85e-01, 1.10e+02],
         [4.06e-01, 1.22e+02], [4.26e-01, 1.33e+02]])
    data2_4 = np.array(
        [[2.02e-05, -6.50e-02], [1.59e-02, 8.46e+00], [3.76e-02, 1.68e+01], [5.82e-02, 2.43e+01], [7.86e-02, 3.34e+01],
         [9.90e-02, 4.54e+01], [1.19e-01, 6.11e+01], [1.40e-01, 8.16e+01], [1.60e-01, 1.06e+02], [1.80e-01, 1.34e+02],
         [2.01e-01, 1.65e+02], [2.21e-01, 1.96e+02], [2.41e-01, 2.26e+02]])
    np.savetxt("6.txt", data0_6)
    np.savetxt("2.txt", data1_2)
    np.savetxt("4.txt", data2_4)

    app = QtWidgets.QApplication(sys.argv)
    if sys.platform.startswith('win'):
        import ctypes
        myappid = 'fabrylab.saenopy.master'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    print(sys.argv)
    window = MainWindowFit()
    window.setMinimumWidth(1600)
    window.setMinimumHeight(900)
    window.setWindowTitle("Saenopy Viewer")
    window.setWindowIcon(resource_icon("Icon.ico"))
    window.show()
    window.add_file("6.txt")
    window.add_file("2.txt")
    window.add_file("4.txt")
    sys.exit(app.exec_())
