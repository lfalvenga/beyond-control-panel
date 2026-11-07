from datetime import datetime


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')

def today_br() -> str:
    return datetime.now().strftime('%d/%m/%Y')