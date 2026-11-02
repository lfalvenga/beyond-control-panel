def setter(obj, attribute: str, then):
    """Devolve um tratador que grava o novo valor no objeto e chama `then`."""

    def handler(event):
        setattr(obj, attribute, event.value)
        then()

    return handler