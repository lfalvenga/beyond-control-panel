class SessionState:
    """Estado da sessão da interface: operação ativa, operação em edição e quem escuta as mudanças."""

    def __init__(self) -> None:
        self.active_code: str | None = None  # operação em uso (Telemetria, Log, Relatório)
        self.editing_code: str | None = None  # operação aberta no Cadastro (None = nova)
        self._on_active: list = []
        self._on_editing: list = []
        self._on_list: list = []
        self._on_data: list = []
        self.navigate = lambda page: None  # o shell troca por uma navegação de verdade
        # o Cadastro troca por uma guarda que avisa de alterações não salvas
        self.edit_guard = lambda code: self.edit(code, force=True)

    def on_active_change(self, callback) -> None:
        self._on_active.append(callback)

    def on_editing_change(self, callback) -> None:
        self._on_editing.append(callback)

    def on_list_change(self, callback) -> None:
        self._on_list.append(callback)

    def on_data_change(self, callback) -> None:
        self._on_data.append(callback)

    def activate(self, code: str | None, force: bool = False) -> None:
        if code == self.active_code and not force:
            return
        self.active_code = code
        for callback in list(self._on_active):
            callback()

    def edit(self, code: str | None, force: bool = False) -> None:
        if code == self.editing_code and not force:
            return
        self.editing_code = code
        for callback in list(self._on_editing):
            callback()

    def request_edit(self, code: str | None) -> None:
        """Pede para abrir `code` no Cadastro (None = nova). Passa pela guarda."""
        self.edit_guard(code)

    def list_changed(self) -> None:
        for callback in list(self._on_list):
            callback()

    def data_changed(self) -> None:
        """Os dados (fontes, gravações) da operação ativa mudaram."""
        for callback in list(self._on_data):
            callback()