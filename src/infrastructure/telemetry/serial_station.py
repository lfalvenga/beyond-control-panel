import queue
import threading

import serial
import serial.tools.list_ports


class SerialStation:
    """Adaptador da porta serial: a leitura roda numa thread e só enfileira linhas."""

    def __init__(self) -> None:
        self.is_open = False
        self._lines: queue.Queue = queue.Queue()
        self._errors: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._port = None

    def list_ports(self) -> list[tuple[str, str]]:
        return [
            (p.device, f'{p.device} · {p.description}')
            for p in serial.tools.list_ports.comports()
        ]

    def open(self, port: str, baud: int) -> None:
        self.close()
        while not self._lines.empty():
            self._lines.get_nowait()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read, args=(self._stop, port, baud), daemon=True)
        self._thread.start()
        self.is_open = True

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self.is_open = False

    def read_lines(self) -> list[str]:
        lines = []
        while not self._lines.empty():
            lines.append(self._lines.get_nowait())
        return lines

    def take_error(self) -> str:
        message = ''
        while not self._errors.empty():
            message = self._errors.get_nowait()
        if message:
            self.is_open = False
        return message

    def write_line(self, text: str) -> None:
        port = self._port
        if port is None:
            raise ConnectionError('A estação não está conectada.')
        try:
            port.write((text + '\n').encode('utf-8'))
            port.flush()
        except (serial.SerialException, OSError) as error:
            raise ConnectionError(f'Falha ao enviar: {error}') from error

    def _read(self, stop: threading.Event, port: str, baud: int) -> None:
        try:
            with serial.Serial(port, baud, timeout=0.5) as connection:
                self._port = connection
                buffer = b''
                while not stop.is_set():
                    chunk = connection.readline()
                    if not chunk:
                        continue
                    buffer += chunk
                    if len(buffer) > 65536:  # lixo sem fim de linha: descarta
                        buffer = b''
                        continue
                    if not buffer.endswith(b'\n'):
                        continue  # linha ainda incompleta
                    line = buffer.decode('utf-8', errors='replace').strip()
                    buffer = b''
                    if line:
                        self._lines.put(line)
        except (serial.SerialException, OSError) as error:
            if not stop.is_set():
                self._errors.put(str(error))
        finally:
            self._port = None