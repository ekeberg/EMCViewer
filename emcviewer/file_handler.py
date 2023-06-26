import os
import pathlib
import re
import time

from PyQt5 import QtCore
from eke import sphelper


def mtime(filename):
    return pathlib.Path(filename).stat().st_mtime

class FileCaching(QtCore.QThread):
    def __init__(self, data_dir, file_filter, cache_limit=100):
        super().__init__()
        self.index = []
        self.data = []
        self.mtime = []

        self._cache_limit = cache_limit

        self._running = True
        self._paused = False
        self.file_list = None

        self._data_dir = data_dir
        self._file_filter = file_filter
        self.current_index = 10
        self.update_file_list()

    def change_data_dir(self, new_dir):
        # print("Change data dir")
        self._data_dir = new_dir
        # Reset the cache. Later could possibly be saved as an
        # alternate cache, if we do a lot of switching.
        self.index = []
        self.data = []
        self.mtime = []
        self.update_file_list()

        filename = os.path.join(self._data_dir,
                                self.file_list[self.current_index])
        data = sphelper.import_spimage(filename, ["image"])
        self.index.append(self.current_index)
        self.data.append(data)
        self.mtime.append(mtime(filename))

    def update_file_list(self):
        new_file_list = [f for f in os.listdir(self._data_dir)
                         if re.search(self._file_filter, f)]
        new_file_list.sort()
        if len(new_file_list) == 0:
            raise ValueError(f"Directory {self._data_dir} does not contain "
                             f"any files matching {self._file_filter}")

        if self.file_list is not None:
            if self.file_list == new_file_list:
                return
            current_file_name = self.file_list[self.current_index]
        else:
            current_file_name = new_file_list[-1]

        # Update index
        original_length = len(self.index)
        for i in range(len(self.index)):
            inv_i = original_length - i - 1
            fname = self.file_list[self.index[inv_i]]
            if fname not in new_file_list:
                del self.index[inv_i]
                del self.data[inv_i]
                del self.mtime[inv_i]
            else:
                self.index[inv_i] = new_file_list.index(fname)

        self.file_list = new_file_list
        if current_file_name in self.file_list:
            self.current_index = self.file_list.index(current_file_name)
        else:
            self.current_index = len(self.file_list) - 1

    def run(self):
        # print("Start file cacher")
        while self._running:
            # print("Cache loop is running!")
            if self._paused:
                print("Sleeping: paused")
                time.sleep(0.5)
                continue

            # Remove outdated files
            original_length = len(self.index)
            for file_index in range(original_length):
                # Go backwards to avoid index shifting
                inv_index = original_length - file_index - 1
                file_path = os.path.join(self._data_dir,
                                         self.file_list[self.index[inv_index]])
                modification_time = mtime(file_path)
                if self.mtime[inv_index] != modification_time:
                    del self.index[inv_index]
                    del self.data[inv_index]
                    del self.mtime[inv_index]

            load_index = self.current_index + 1
            self.update_file_list()

            # Do some check of if the current index changed (or put in
            # update_file_list
            if len(self.index) >= len(self.file_list):
                time.sleep(0.5)
                continue

            while (load_index in self.index or
                   load_index < 0 or
                   load_index >= len(self.file_list)):
                load_index = (2*self.current_index
                              - load_index
                              + (1 if load_index < self.current_index else 0))
                if abs(load_index - self.current_index) > self._cache_limit:
                    break

            if load_index < 0 or load_index >= len(self.file_list):
                continue

            while len(self.index) > self._cache_limit:
                distance = [abs(i - self.current_index) for i in self.index]
                max_distance = max(distance)
                index_to_del = distance.index(max_distance)
                del self.index[index_to_del]
                del self.data[index_to_del]
                del self.mtime[index_to_del]

            if len(self.index) == self._cache_limit:
                distance = [abs(i - self.current_index) for i in self.index]
                max_distance = max(distance)
                if abs(load_index-self.current_index) >= max_distance:
                    # print("Sleeping: Cache is full")
                    time.sleep(0.5)
                    continue
                index_to_del = distance.index(max_distance)
                del self.index[index_to_del]
                del self.data[index_to_del]
                del self.mtime[index_to_del]

            # print(f"Cache data {load_index}")
            filename = os.path.join(self._data_dir, self.file_list[load_index])
            data = sphelper.import_spimage(filename, ["image"])
            self.index.append(load_index)
            self.data.append(data)
            self.mtime.append(mtime(filename))

    def get_data(self, index):
        self.current_index = index
        if index in self.index:
            # print(f"Load {index} cached")
            return self.data[self.index.index(index)]
        else:
            # print(f"Load {index} from file")
            # print(f"Currently cached: {self.index}")
            filename = os.path.join(self._data_dir, self.file_list[index])
            data = sphelper.import_spimage(filename, ["image"])
            self.index.append(index)
            self.data.append(data)
            self.mtime.append(mtime(filename))
            return data

    def pause(self):
        self._paused = True

    def unpause(self):
        self._paused = False

    def exit(self):
        # print("exit cacher")
        self._running = False
        super().exit()
        # print("finished exit cacher")