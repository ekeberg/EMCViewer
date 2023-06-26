import numpy
import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtGui, QtCore, QtWidgets
import os
import argparse
import sys
from eke import vtk_tools

from emcviewer import file_handler
# import file_handler


class PlaneTool:
    def __init__(self, vtk_widget, image_data):
        self._vtk_widget = vtk_widget
        self._image_data = image_data
        self._cmap_dict = {"log": False,
                           "vmin": 0,
                           "vmax": 1}


        self.setup_plane()

    def setup_plane(self):
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
        self._plane.SetSliceIndex(self._image_data.GetDimensions()[2]//2)
        self._plane.SetEnabled(1)

        # self._vtk_window.Render()
        self._vtk_widget.GetRenderWindow().Render()

    def set_visible(self, state):
        self._plane.SetEnabled(state)
        # if state:
        #     self._plane.TextureVisibilityOn()
        # else:
        #     self._plane.TextureVisibilityOff()
        self._vtk_widget.GetRenderWindow().Render()

    def reset_plane(self):
        self._plane.SetPlaneOrientationToZAxes()
        self._plane.SetSliceIndex(self._image_data.GetDimensions()[2]//2)
        self._plane.Modified()
        # self._vtk_window.Render()
        self._vtk_widget.GetRenderWindow().Render()

    def refresh_lut(self):
        if self._cmap_dict["log"]:
            self._lut.SetRange(max(self._cmap_dict["vmin"], 0),
                               self._cmap_dict["vmax"])
            self._lut.SetScaleToLog10()
        else:
            self._lut.SetScaleToLinear()
            self._lut.SetRange(self._cmap_dict["vmin"],
                               self._cmap_dict["vmax"])
        self._lut.Modified()
        # self._vtk_window.Render()
        self._vtk_widget.GetRenderWindow().Render()

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
        vmin, vmax = self._image_data.GetScalarRange()
        self._cmap_dict["vmin"] = vmin
        self._cmap_dict["vmax"] = vmax
        self.refresh_lut()


class PlaneToolControls(QtWidgets.QWidget):
    def __init__(self, plane_tool):
        super().__init__()
        self._plane_tool = plane_tool

        self._logscale_box = QtWidgets.QCheckBox("Logscale")
        self._logscale_box.stateChanged.connect(self._on_log_scale)

        float_validator = QtGui.QDoubleValidator()
        self._cmap_min_edit = QtWidgets.QLineEdit("0.0")
        self._cmap_min_edit.setValidator(float_validator)
        self._cmap_max_edit = QtWidgets.QLineEdit("1.0")
        self._cmap_max_edit.setValidator(float_validator)
        self._cmap_min_edit.textChanged.connect(self._on_vmin_change)
        self._cmap_max_edit.textChanged.connect(self._on_vmax_change)
        self._update_cmap_button = QtWidgets.QPushButton("Update cmap")
        self._update_cmap_button.clicked.connect(self._on_cmap_auto)

        self._reset_plane_button = QtWidgets.QPushButton("Reset plane")
        self._reset_plane_button.clicked.connect(self._plane_tool.reset_plane)

        layout = QtWidgets.QGridLayout()

        layout.addWidget(self._cmap_min_edit, 0, 0)
        layout.addWidget(self._update_cmap_button, 0, 1)
        layout.addWidget(self._cmap_max_edit, 0, 2)
        layout.addWidget(self._logscale_box, 0, 3)
        layout.addWidget(self._reset_plane_button, 1, 0)

        self.setLayout(layout)

    def _on_log_scale(self, state):
        self._plane_tool.cmap_log = state

    def _on_vmin_change(self, vmin):
        try:
            vmin = float(vmin)
        except ValueError:
            return
        self._plane_tool.cmap_vmin = vmin

    def _on_vmax_change(self, vmax):
        try:
            vmax = float(vmax)
        except ValueError:
            return
        self._plane_tool.cmap_vmax = vmax

    def _on_cmap_auto(self):
        self._plane_tool.cmap_auto()
        self._cmap_min_edit.setText(str(self._plane_tool.cmap_vmin))
        self._cmap_max_edit.setText(str(self._plane_tool.cmap_vmax))


class IsosurfaceTool:
    def __init__(self, vtk_widget, image_data):
        self._vtk_widget = vtk_widget
        self._image_data = image_data

        self._surface_algorithm = vtk.vtkMarchingCubes()
        self._surface_algorithm.SetInputData(self._image_data)
        self._surface_algorithm.ComputeNormalsOn()
        self._surface_algorithm.SetValue(0, 0.1)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(self._surface_algorithm.GetOutputPort())
        mapper.ScalarVisibilityOff()
        self.actor = vtk.vtkActor()
        self.actor.GetProperty().SetColor(0., 1., 0.)
        self.actor.SetMapper(mapper)
        self.actor.SetVisibility(False)
        # self._renderer.AddViewProp(self._actor)

    def set_visible(self, state):
        self.actor.SetVisibility(bool(state))
        self._vtk_widget.GetRenderWindow().Render()

    def set_level(self, level):
        data_max = self._image_data.GetScalarRange()[1]
        surface_level = level*data_max
        self._surface_algorithm.SetValue(0, surface_level)
        self._surface_algorithm.Modified()
        self._vtk_widget.GetRenderWindow().Render()


class IsosurfaceToolControls(QtWidgets.QWidget):
    def __init__(self, plane_tool):
        super().__init__()
        self._isosurface_tool = plane_tool

        self._level_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._level_slider.setMaximum(10000)
        self._level_slider.valueChanged.connect(
            lambda x: self._isosurface_tool.set_level(x/10000))

        layout = QtWidgets.QGridLayout()
        layout.addWidget(self._level_slider, 0, 0)
        self.setLayout(layout)


class View3DWidget(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None

        self._vtk_widget = QVTKRenderWindowInteractor(self)
        self._vtk_widget.SetInteractorStyle(
            vtk.vtkInteractorStyleRubberBandPick())

        self._renderer = vtk.vtkRenderer()
        self._renderer.SetBackground(0., 0., 0.)

        self._vtk_widget.Initialize()
        self._vtk_widget.Start()

        self._vtk_window = self._vtk_widget.GetRenderWindow()
        self._vtk_window.AddRenderer(self._renderer)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._vtk_widget)

        self.setLayout(layout)

        self._image_data = vtk.vtkImageData()
        self._data = numpy.ascontiguousarray(
            numpy.zeros((5, 5, 5), dtype="float32"))
        self._setup_float_array(self._data)

        self.plane_tool = PlaneTool(self._vtk_widget, self._image_data)
        self.isosurface_tool = IsosurfaceTool(self._vtk_widget,
                                              self._image_data)
        self._renderer.AddViewProp(self.isosurface_tool.actor)

        self._vtk_window.Render()

    def _setup_float_array(self, data):
        self._float_array = vtk.vtkFloatArray()
        self._float_array.SetNumberOfComponents(1)
        self._float_array.SetVoidArray(
            data, int(numpy.product(self._data.shape)), 1)
        self._image_data.SetDimensions(*data.shape)
        self._image_data.GetPointData().SetScalars(self._float_array)

    def set_data(self, data):
        if self._data is None or self._data.shape != data.shape:
            self._data = numpy.ascontiguousarray(data, dtype="float32")
            self._setup_float_array(self._data)

            self.plane_tool.reset_plane()

            camera = self._renderer.GetActiveCamera()
            camera.SetFocalPoint(*(s/2 for s in self._data.shape))
            camera.SetPosition(self._data.shape[0]/2,
                               self._data.shape[1]/2,
                               self._data.shape[2]*2)
            camera.SetViewUp(1., 0., 0.)
            camera.SetClippingRange(0.01, 1000000000)
        else:
            self._data[:] = data
            self._float_array.Modified()
            self._vtk_window.Render()

    def reset_camera(self):
        camera = self._renderer.GetActiveCamera()
        camera.SetFocalPoint(*(s/2 for s in self._data.shape))
        camera.SetPosition(self._data.shape[0]/2,
                           self._data.shape[1]/2,
                           self._data.shape[2]*2*2)
        camera.SetClippingRange(0.01, 1000000000)
        camera.SetViewUp(1., 0., 0.)
        camera.Modified()
        self._vtk_window.Modified()
        self._vtk_window.Render()
        self._vtk_widget.Render()





class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, data_dir, file_filter=None):
        super(MainWindow, self).__init__()

        file_filter = file_filter if file_filter else "model.*.h5$"
        self._file_cacher = file_handler.FileCaching(data_dir, file_filter, 100)
        self._file_cacher.start()

        self._setup_gui()
        self._setup_menu()
        self._setup_shortcuts()

        if os.path.isdir(data_dir):
            self._data_dir = data_dir
            self._file_cacher.update_file_list()
            self._update_file_combobox()
            self._load_file(len(self._file_cacher.file_list)-1)
        elif os.path.isfile(data_dir):
            self._data_dir, this_file = os.path.split(data_dir)
            self._file_cacher.update_file_list()
            self._update_file_combobox()
            self._load_file(self._file_cacher.file_list.index(this_file))
        else:
            raise ValueError(f"Can not load, {data_dir} is not a directory "
                             "or file")

        self._file_list_timer = QtCore.QTimer()
        self._file_list_timer.timeout.connect(self._on_timer)
        self._file_list_timer.start(1000)

    def _setup_gui(self):
        self._view3d_widget = View3DWidget()

        self._prev_button = QtWidgets.QPushButton("Previous")
        self._next_button = QtWidgets.QPushButton("Next")
        self._prev_button.clicked.connect(self._on_model_prev)
        self._next_button.clicked.connect(self._on_model_next)

        self._filename_combobox = QtWidgets.QComboBox(self)
        self._filename_combobox.activated[str].connect(
            self._on_combobox_change)

        self._reset_camera_button = QtWidgets.QPushButton("Reset camera")
        self._reset_camera_button.clicked.connect(
            self._view3d_widget.reset_camera)

        self._plane_tool_controls = PlaneToolControls(
            self._view3d_widget.plane_tool)
        self._isosurface_tool_controls = IsosurfaceToolControls(
            self._view3d_widget.isosurface_tool)

        self._plane_tool_checkbox = QtWidgets.QCheckBox("Plane")
        self._plane_tool_checkbox.stateChanged.connect(
            self._on_plane_visibility)
        self._plane_tool_checkbox.setChecked(True)

        self._isosurface_tool_checkbox = QtWidgets.QCheckBox("Isosurface")
        self._isosurface_tool_checkbox.stateChanged.connect(
            self._on_isosurface_visibility)
        self._isosurface_tool_checkbox.setChecked(False)

        layout = QtWidgets.QGridLayout()

        layout.addWidget(self._view3d_widget, 0, 0, 1, 3)
        layout.addWidget(self._prev_button, 1, 0)
        layout.addWidget(self._filename_combobox, 1, 1)
        layout.addWidget(self._next_button, 1, 2)

        layout.addWidget(self._reset_camera_button, 2, 1)

        layout.addWidget(self._plane_tool_checkbox, 3, 0)
        layout.addWidget(self._plane_tool_controls, 4, 0, 1, 3)
        layout.addWidget(self._isosurface_tool_checkbox, 5, 0)
        layout.addWidget(self._isosurface_tool_controls, 6, 0, 1, 3)
        self._isosurface_tool_controls.setVisible(False)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

    def _on_plane_visibility(self, state):
        self._view3d_widget.plane_tool.set_visible(state)
        self._plane_tool_controls.setVisible(state)

    def _on_isosurface_visibility(self, state):
        self._view3d_widget.isosurface_tool.set_visible(state)
        self._isosurface_tool_controls.setVisible(state)

    def _setup_shortcuts(self):
        self._next_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("right"),
                                                  self._next_button)
        self._next_shortcut.activated.connect(self._on_model_next)
        self._prev_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("left"),
                                                  self._prev_button)
        self._prev_shortcut.activated.connect(self._on_model_prev)

    def _on_timer(self):
        self._file_cacher.update_file_list()
        self._update_file_combobox()

    def _on_combobox_change(self, text):
        # self._file_index = self._file_list.index(text)
        # self._load_file(self._file_list.index(text))
        self._load_file(self._filename_combobox.currentIndex())

    def _setup_menu(self):
        # menubar = QtWidgets.QMenuBar()
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QtWidgets.QAction("&Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_dir)
        file_menu.addAction(open_action)
        quit_action = QtWidgets.QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self._on_quit)
        file_menu.addAction(quit_action)

    def _on_quit(self):
        # print("Quit gracefully")
        self._file_cacher.exit()
        # print("exit app")
        QtWidgets.qApp.quit()
        # print("finished exit app")

    def _on_open_dir(self):
        self._file_cacher.pause()
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Folder")
        if new_dir:
            self._file_cacher.change_data_dir(new_dir)
        self._file_cacher.unpause()

    def _update_file_combobox(self):
        self._filename_combobox.clear()
        for f in self._file_cacher.file_list:
            self._filename_combobox.addItem(os.path.split(f)[1])
        self._filename_combobox.setCurrentIndex(
            self._file_cacher.current_index)

    def _load_file(self, file_index):
        self._filename_combobox.setCurrentIndex(file_index)
        data = self._file_cacher.get_data(file_index)
        self._view3d_widget.set_data(data)

    def _on_model_next(self):
        if (
                self._file_cacher.current_index + 1
                < len(self._file_cacher.file_list)
        ):
            self._load_file(self._file_cacher.current_index + 1)

    def _on_model_prev(self):
        if self._file_cacher.current_index - 1 >= 0:
            self._load_file(self._file_cacher.current_index - 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=str, nargs="?", default=".")
    parser.add_argument("--filter", type=str, default=None)
    args = parser.parse_args()

    app = QtWidgets.QApplication(["EMCviewer"])
    app.setApplicationName("EMCviewer")

    program = MainWindow(args.data_dir, file_filter=args.filter)
    program.resize(1024, 1024)
    program.show()
    program.activateWindow()
    program.raise_()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


# TODO:
# * Reset file list when changing dictionary
# ~ Check age of file when caching
# * Pause caching when opening file dialog (this might be what is
#   slowing it down.
# * Error message at startup
# * Exit on command
#
