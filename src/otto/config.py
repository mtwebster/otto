from gi.repository import Gio


SCHEMA_ID = 'org.x.Otto'


class Settings:
    def __init__(self):
        self._s = Gio.Settings.new(SCHEMA_ID)

    @property
    def delay(self) -> int:
        return self._s.get_int('delay')

    @delay.setter
    def delay(self, value: int) -> None:
        self._s.set_int('delay', value)

    @property
    def include_pointer(self) -> bool:
        return self._s.get_boolean('include-pointer')

    @include_pointer.setter
    def include_pointer(self, value: bool) -> None:
        self._s.set_boolean('include-pointer', value)

    @property
    def auto_save_directory(self) -> str:
        return self._s.get_string('auto-save-directory')

    @property
    def last_save_directory(self) -> str:
        return self._s.get_string('last-save-directory')

    @last_save_directory.setter
    def last_save_directory(self, value: str) -> None:
        self._s.set_string('last-save-directory', value)

    @property
    def default_file_type(self) -> str:
        return self._s.get_string('default-file-type')

    @default_file_type.setter
    def default_file_type(self, value: str) -> None:
        self._s.set_string('default-file-type', value)
