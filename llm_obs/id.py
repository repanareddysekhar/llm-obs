import ulid


def new_id() -> str:
    return str(ulid.new())
