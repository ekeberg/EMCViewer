import numpy
import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtGui, QtCore, QtWidgets
import os
import re
import argparse
import sys
from eke import vtk_tools
from eke import sphelper


class SliceWidget(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__()
        self._data = None
        self._cmap_dict = {"log": False,
                           "vmin": 0,
                           "vmax": 1}

        self._vtk_widget = QVTKRenderWindowInteractor(self)
        self._vtk_widget.SetInteractorStyle(vtk.vtkInteractorStyleRubberBandPick())

        self._renderer = vtk.vtkRenderer()
        self._renderer.SetBackground(0., 0., 0.)

        self._vtk_widget.Initialize()
        self._vtk_widget.Start()
        
        self._vtk_window = self._vtk_widget.GetRenderWindow()
        self._vtk_window.AddRenderer(self._renderer)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._vtk_widget)

        self.setLayout(layout)
        
        self._vtk_window.Render()


    def set_data(self, data):
        if self._data is None or self._data.shape != data.shape:
            self._data = numpy.ascontiguousarray(data, dtype="float32")
            self._float_array = vtk.vtkFloatArray()
            self._float_array.SetNumberOfComponents(1)
            self._float_array.SetVoidArray(self._data, int(numpy.product(self._data.shape)), 1)

            self._image_data = vtk.vtkImageData()
            self._image_data.SetDimensions(*self._data.shape)
            self._image_data.GetPointData().SetScalars(self._float_array)
            self._setup_plane()

            camera = self._renderer.GetActiveCamera()
            camera.SetFocalPoint(*(s/2 for s in self._data.shape))
            camera.SetPosition(self._data.shape[0]/2, self._data.shape[1]/2, self._data.shape[2]*2)
        else:
            self._data[:] = data
            self._float_array.Modified()
            self._vtk_window.Render()

    def _setup_plane(self):
        self._lut = vtk_tools.get_lookup_table(0, 1, colorscale="viridis")
        
        self._picker = vtk.vtkCellPicker()
        self._picker.SetTolerance(0.005)


        self._plane = vtk.vtkImagePlaneWidget()
        self._plane.SetInputData(self._image_data)

        self._plane.UserControlledLookupTableOn()
        self._plane.SetLookupTable(self._lut)
        self._plane.DisplayTextOn()
        self._plane.SetPicker(self._picker)
        self._plane.SetLeftButtonAction(1)
        self._plane.SetMiddleButtonAction(2)
        self._plane.SetRightButtonAction(0)
        self._plane.SetInteractor(self._vtk_widget)
        self._plane.SetPlaneOrientationToZAxes()
        self._plane.SetSliceIndex(self._data.shape[2]//2)
        self._plane.SetEnabled(1)

        self._vtk_window.Render()

    def refresh_lut(self):
        if self._cmap_dict["log"]:
            self._lut.SetRange(max(self._cmap_dict["vmin"], 0), self._cmap_dict["vmax"])
            self._lut.SetScaleToLog10()
        else:
            self._lut.SetScaleToLinear()
            self._lut.SetRange(self._cmap_dict["vmin"], self._cmap_dict["vmax"])
        self._lut.Modified()
        self._vtk_window.Render()

    @property
    def cmap_vmin(self):
        return self._cmap_dict["vmin"]

    @property
    def cmap_vmax(self):
        return self._cmap_dict["vmax"]

    @property
    def cmap_log(self):
        return self._cmap_dict["log"]

    @cmap_vmin.setter
    def cmap_vmin(self, value):
        self._cmap_dict["vmin"] = value
        self.refresh_lut()

    @cmap_vmax.setter
    def cmap_vmax(self, value):
        self._cmap_dict["vmax"] = value
        self.refresh_lut()

    @cmap_log.setter
    def cmap_log(self, state):
        self._cmap_dict["log"] = state
        self.refresh_lut()

    def cmap_auto(self):
        self._cmap_dict["vmin"] = self._data.min()
        self._cmap_dict["vmax"] = self._data.max()
        self.refresh_lut()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data_dir):
        super(MainWindow, self).__init__()
        self._data_dir = data_dir

        self.update_file_list()
        self._file_index = len(self.file_list) - 1

        self._slice_widget = SliceWidget()
        
        self._prev_button = QtWidgets.QPushButton("Previous")
        self._prev_button.clicked.connect(self._on_model_prev)
        self._next_button = QtWidgets.QPushButton("Next")
        self._next_button.clicked.connect(self._on_model_next)

        self._filename_label = QtWidgets.QLabel("")
        self._filename_combobox = QtWidgets.QComboBox(self)
        for f in self.file_list:
            self._filename_combobox.addItem(os.path.split(f)[1])
        self._filename_combobox.setCurrentIndex(self._file_index)
        self._filename_combobox.activated[str].connect(self._on_combobox_change)

        self._logscale_box = QtWidgets.QCheckBox("Log:")
        def set_log(state): self._slice_widget.cmap_log = state
        self._logscale_box.stateChanged.connect(set_log)

        float_validator = QtGui.QDoubleValidator()
        self._cmap_min_edit = QtWidgets.QLineEdit("0.0")
        self._cmap_min_edit.setValidator(float_validator)
        self._cmap_max_edit = QtWidgets.QLineEdit("1.0")
        self._cmap_max_edit.setValidator(float_validator)
        self._cmap_min_edit.textChanged.connect(self._on_vmin_change)
        self._cmap_max_edit.textChanged.connect(self._on_vmax_change)
        self._update_cmap_button = QtWidgets.QPushButton("Update cmap")
        self._update_cmap_button.clicked.connect(self._on_cmap_auto)

        layout_2 = QtWidgets.QHBoxLayout()
        layout_2.addWidget(self._prev_button)
        layout_2.addWidget(self._filename_combobox)
        layout_2.addWidget(self._next_button)

        layout_3 = QtWidgets.QHBoxLayout()
        layout_3.addWidget(self._logscale_box)
        layout_3.addWidget(self._cmap_min_edit)
        layout_3.addWidget(self._update_cmap_button)
        layout_3.addWidget(self._cmap_max_edit)
        
        layout_1 = QtWidgets.QVBoxLayout()
        layout_1.addWidget(self._slice_widget)
        layout_1.addLayout(layout_2)
        layout_1.addLayout(layout_3)
        
        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout_1)

        self.setCentralWidget(central_widget)

        self.load_file(self.file_list[self._file_index])

    def _on_combobox_change(self, text):
        self._file_index = self.file_list.index(text)
        self.load_file(text)

    def _on_vmin_change(self, vmin):
        try:
            vmin = float(vmin)
        except(ValueError):
            return 
        self._slice_widget.cmap_vmin = vmin

    def _on_vmax_change(self, vmax):
        try:
            vmax = float(vmax)
        except(ValueError):
            return 
        self._slice_widget.cmap_vmax = vmax

    def _on_cmap_auto(self):
        self._slice_widget.cmap_auto()
        self._cmap_min_edit.setText(str(self._slice_widget.cmap_vmin))
        self._cmap_max_edit.setText(str(self._slice_widget.cmap_vmax))
        
    def update_file_list(self):
        self.file_list = [f for f in os.listdir(self._data_dir)
                          if re.search("model.+h5$", f)]

    def load_file(self, file_name):
        data = sphelper.import_spimage(os.path.join(self._data_dir, file_name), ["image"])
        self._slice_widget.set_data(data)
        self._filename_label.setText(file_name)
        
    def _on_model_next(self):
        if self._file_index + 1 < len(self.file_list):
            self._file_index += 1
            self._filename_combobox.setCurrentIndex(self._file_index)
            self.load_file(self.file_list[self._file_index])

    def _on_model_prev(self):
        if self._file_index - 1 >= 0:
            self._file_index -= 1
            self._filename_combobox.setCurrentIndex(self._file_index)
            self.load_file(self.file_list[self._file_index])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=str)
    args = parser.parse_args()

    app = QtWidgets.QApplication([f"EMCviewer"])
    app.setApplicationName("EMCviewer")

    program = MainWindow(args.data_dir)
    program.resize(1024, 1024)
    program.show()
    program.activateWindow()
    program.raise_()
    sys.exit(app.exec_())
